"""Exact range of Fleiss' kappa over all legal category assignments.

A *candidate vote* ("备选票") keeps its originally recorded category but is
limited to a declared set of allowed categories instead of one final label.
The ordinary definite-vote analysis is untouched and keeps using the original
label only; this module is a separate exhaustive calculation.

For fixed N specimens, r=3 raters and category totals T_j the exact value is

    S = sum_i sum_j n_ij * (n_ij - 1)          (twice the pair-agreement sum)
    T = sum_j (sum_i n_ij) ** 2
    kappa = (3*N*S - 2*T) / (2*((3*N)**2 - T))

so for every final category-total vector only the smallest and largest
reachable S are needed.  A dynamic programme over the number of candidate
votes assigned to each category visits every legal assignment implicitly and
computes the true minimum and maximum with rational arithmetic.  It is not a
sample, not a bootstrap and never substitutes a point estimate for the range.

Guards refuse the work (with an explicit ``AlternativesRefused`` error) before
or during the computation when exact enumeration would exceed the documented
time/memory envelope.  A refusal never returns an approximate range.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
from math import comb
import hashlib
import json
import resource
import time

RATERS_PER_SPECIMEN = 3
FINGERPRINT_VERSION = 'alternatives-exact-dp-v1'
FORMULA = ('kappa=(3*N*S-2*T)/(2*((3*N)^2-T)); '
           'S=sum_i sum_j n_ij*(n_ij-1); '
           'T=sum_j(category_total_j^2); N specimens, 3 raters')

# Documented workload: 240 specimens, 3 categories, 48 candidate votes with 3
# alternatives each -> 1225 states and well under 100k transitions.
MAX_STATES = 400_000
MAX_TRANSITIONS = 3_000_000
MAX_PARENT_BYTES = 96 * 1024 * 1024
PARENT_ENTRY_BYTES = 144  # dict entry + two Python ints, conservative
DEFAULT_DEADLINE_SECONDS = 25.0
DEFAULT_MEMORY_LIMIT_MB = 256
MEMORY_HEADROOM_MB = 16


class AlternativesAnalysisError(ValueError):
    """Invalid input or inconsistent internal result for an alternatives run."""


class AlternativesRefused(AlternativesAnalysisError):
    """Exact work exceeds the documented time/memory guard.

    The caller must surface this refusal.  No partial assignment and no
    approximate kappa may be returned.
    """

    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def _compositions(total, parts):
    """All vectors of ``parts`` non-negative integers summing to ``total``."""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _compositions(total - first, parts - 1):
            yield (first,) + rest


def _rss_mb():
    """Current resident set size in MB (Linux /proc, portable fallback)."""
    try:
        with open('/proc/self/statm', encoding='ascii') as handle:
            pages = int(handle.read().split()[1])
        return pages * resource.getpagesize() / (1024.0 * 1024.0)
    except (OSError, ValueError, IndexError):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _decimal_text(value, places=18):
    with localcontext() as context:
        context.prec = 40
        rendered = format(Decimal(value.numerator) / Decimal(value.denominator), f'.{places}f')
    if '.' in rendered:
        rendered = rendered.rstrip('0').rstrip('.')
    return rendered or '0'


def _rational(value):
    return {
        'numerator': value.numerator,
        'denominator': value.denominator,
        'text': f'{value.numerator}/{value.denominator}',
        'decimal': _decimal_text(value),
        'float': float(value),
    }


def fraction_from_rational(payload):
    return Fraction(payload['numerator'], payload['denominator'])


def fingerprint_alternatives(study, specimens, votes, config):
    payload = {
        'version': FINGERPRINT_VERSION,
        'study': study,
        'specimens': sorted(specimens, key=lambda s: s['reference']),
        'votes': sorted(
            ({**v, 'alternatives': list(v['alternatives']) if v.get('alternatives') else None}
             for v in votes),
            key=lambda v: (v['specimen_id'], v['rater'])),
        'config': config,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True,
                   separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _prepare(study, specimens, votes):
    categories = list(study['categories'])
    raters = list(study['raters'])
    category_index = {c: i for i, c in enumerate(categories)}
    if len(category_index) != len(categories) or not 2 <= len(categories) <= 6:
        raise AlternativesAnalysisError('类别须为2..6个唯一声明')
    if len(raters) != RATERS_PER_SPECIMEN or len(set(raters)) != len(raters):
        raise AlternativesAnalysisError('备选票分析须固定3位唯一标记者')
    ordered = sorted(specimens, key=lambda s: s['reference'])
    if not 2 <= len(ordered) <= 240:
        raise AlternativesAnalysisError('试样须为2..240个唯一试样')
    lookup = {s['id']: {} for s in ordered}
    for vote in votes:
        if vote['specimen_id'] not in lookup or vote['rater'] not in raters:
            raise AlternativesAnalysisError('票指向未知试样或标记者')
        if vote['rater'] in lookup[vote['specimen_id']]:
            raise AlternativesAnalysisError('同一试样同一标记者只能有一票')
        if vote['category'] not in category_index:
            raise AlternativesAnalysisError('原票类别不在声明类别中')
        lookup[vote['specimen_id']][vote['rater']] = vote
    for specimen in ordered:
        if set(lookup[specimen['id']]) != set(raters):
            raise AlternativesAnalysisError('每试样须同一固定3人面板各一票')
    return categories, raters, category_index, ordered, lookup


def _allowed_indices(category_index, vote):
    """Allowed category indices for a vote, or None for a definite vote."""
    alternatives = vote.get('alternatives')
    if not alternatives:
        return None
    if not isinstance(alternatives, (list, tuple)):
        raise AlternativesAnalysisError('备选类别须为列表')
    allowed = []
    for category in alternatives:
        if not isinstance(category, str) or category not in category_index:
            raise AlternativesAnalysisError('备选类别不在声明类别中')
        index = category_index[category]
        if index in allowed:
            raise AlternativesAnalysisError('备选类别须唯一')
        allowed.append(index)
    if not 2 <= len(allowed) <= len(category_index):
        raise AlternativesAnalysisError('每张备选票须限定2..类别数以内的唯一类别')
    if category_index[vote['category']] not in allowed:
        raise AlternativesAnalysisError('原票类别须属于该票的备选集合')
    allowed.sort()
    return tuple(allowed)


def _collect(categories, raters, category_index, ordered, lookup):
    """Split votes into definite and candidate parts.

    ``definite_totals`` and ``fixed_pair_sum`` cover definite votes (including
    candidate votes with a single allowed category); the dynamic programme
    adds the remaining candidate votes.  Every specimen's definite base counts
    are kept so the per-specimen pair agreement can be recomputed.
    """
    C = len(categories)
    definite_totals = [0] * C
    fixed_pair_sum = 0
    affected = []
    candidate_votes = 0
    legal_schemes = 1
    for specimen in ordered:
        base = [0] * C
        candidates = []
        for rater in raters:
            vote = lookup[specimen['id']][rater]
            allowed = _allowed_indices(category_index, vote)
            original_index = category_index[vote['category']]
            if allowed is None:
                base[original_index] += 1
            else:
                candidates.append((vote, allowed))
                candidate_votes += 1
                legal_schemes *= len(allowed)
        if candidates:
            affected.append((specimen, base, candidates))
        else:
            fixed_pair_sum += sum(value * (value - 1) for value in base)
        for index, value in enumerate(base):
            definite_totals[index] += value
    return (definite_totals, fixed_pair_sum, affected, candidate_votes,
            legal_schemes)


def _local_options(base, candidates, C):
    """Distinct category-count additions for one specimen, deterministic."""
    seen = {}
    for choice in product(*[allowed for _, allowed in candidates]):
        addition = [0] * C
        for index in choice:
            addition[index] += 1
        key = tuple(addition)
        if key not in seen:
            pair_sum = sum(
                (base[index] + addition[index]) * (base[index] + addition[index] - 1)
                for index in range(C))
            seen[key] = (choice, pair_sum)
    return [(key, value[0], value[1]) for key, value in sorted(seen.items())]


def _undefined_categories(categories, raters, ordered, lookup):
    """Categories that admit a legal all-one-category (Pe=1) scheme."""
    fixed = set()
    for specimen in ordered:
        for rater in raters:
            vote = lookup[specimen['id']][rater]
            alternatives = vote.get('alternatives')
            if not alternatives:
                fixed.add(vote['category'])
            elif len(set(alternatives)) == 1:
                fixed.add(alternatives[0])
    if len(fixed) > 1:
        return []
    candidates = sorted(fixed) if fixed else list(categories)
    surviving = []
    for category in candidates:
        allowed_everywhere = True
        for specimen in ordered:
            for rater in raters:
                vote = lookup[specimen['id']][rater]
                alternatives = vote.get('alternatives')
                if alternatives and category not in alternatives:
                    allowed_everywhere = False
                    break
            if not allowed_everywhere:
                break
        if allowed_everywhere:
            surviving.append(category)
    return surviving


def _scale_guards(affected, candidate_votes, C, memory_limit_mb,
                  deadline_seconds, baseline_rss_mb):
    # The solver allocates every composition of 0..A candidate votes, i.e.
    # C(A+C, C) state tuples, and indexes them in a dict.
    state_count = comb(candidate_votes + C, C)
    reachable_states = comb(candidate_votes + C - 1, C - 1)
    transition_bound = 0
    parent_entry_bound = 0
    prefix = 0
    for specimen, base, candidates, options in affected:
        prefix += len(candidates)
        reachable = min(reachable_states, comb(prefix + C - 1, C - 1))
        transition_bound += reachable * len(options)
        parent_entry_bound += reachable
    parent_bytes = parent_entry_bound * 2 * PARENT_ENTRY_BYTES
    guards = {
        'deadline_seconds': deadline_seconds,
        'memory_limit_mb': memory_limit_mb,
        'max_states': MAX_STATES,
        'max_transitions': MAX_TRANSITIONS,
        'state_count': state_count,
        'reachable_state_upper_bound': reachable_states,
        'transition_upper_bound': transition_bound,
        'parent_entry_upper_bound': parent_entry_bound,
        'parent_estimate_bytes': parent_bytes,
    }
    if state_count > MAX_STATES:
        raise AlternativesRefused(
            f'精确计算需{state_count}个计数状态，超过安全上限{MAX_STATES}；已拒绝，未给出近似值',
            state_count=state_count, limit=MAX_STATES)
    if transition_bound > MAX_TRANSITIONS:
        raise AlternativesRefused(
            f'精确计算上界{transition_bound}次状态转移，超过安全上限{MAX_TRANSITIONS}；已拒绝，未给出近似值',
            transition_bound=transition_bound, limit=MAX_TRANSITIONS)
    if parent_bytes > MAX_PARENT_BYTES:
        raise AlternativesRefused(
            f'精确回算路径预计占用{parent_bytes // (1024 * 1024)}MB，超过安全上限；已拒绝，未给出近似值',
            parent_estimate_bytes=parent_bytes, limit=MAX_PARENT_BYTES)
    projected = baseline_rss_mb + parent_bytes / (1024.0 * 1024.0) + 64.0
    if projected > memory_limit_mb:
        raise AlternativesRefused(
            f'精确计算预计常驻内存约{projected:.0f}MB，超过{memory_limit_mb}MB安全上限；已拒绝，未给出近似值',
            projected_rss_mb=projected, limit=memory_limit_mb)
    return guards, state_count


def preflight(study, specimens, votes, deadline_seconds=DEFAULT_DEADLINE_SECONDS,
              memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB):
    """Validate a study and report the exact-work envelope without running it."""
    started = time.monotonic()
    categories, raters, category_index, ordered, lookup = _prepare(
        study, specimens, votes)
    (definite_totals, fixed_pair_sum, affected, candidate_votes,
     legal_schemes) = _collect(
        categories, raters, category_index, ordered, lookup)
    if candidate_votes == 0:
        raise AlternativesAnalysisError('研究没有备选票，请使用原确定票分析')
    local = [(specimen, base, candidates, _local_options(base, candidates, len(categories)))
             for specimen, base, candidates in affected]
    guards, state_count = _scale_guards(
        local, candidate_votes, len(categories), memory_limit_mb, deadline_seconds,
        _rss_mb())
    return {
        'accepted': True,
        'candidate_vote_count': candidate_votes,
        'candidate_specimen_count': len(affected),
        'legal_scheme_count': str(legal_schemes),
        'state_count': state_count,
        'reachable_state_upper_bound': guards['reachable_state_upper_bound'],
        'transition_upper_bound': guards['transition_upper_bound'],
        'parent_entry_upper_bound': guards['parent_entry_upper_bound'],
        'elapsed_seconds': time.monotonic() - started,
        'guards': guards,
    }


def _replay_plan(ordered, raters, categories, lookup, chosen, C):
    """Replay one endpoint assignment and recompute every quantity exactly."""
    totals = [0] * C
    pair_sum = 0
    assignments = []
    for specimen in ordered:
        counts = [0] * C
        votes = []
        for rater in raters:
            vote = lookup[specimen['id']][rater]
            alternatives = vote.get('alternatives')
            if alternatives:
                category = chosen.get(vote['id'])
                if category is None:
                    raise AlternativesAnalysisError('回算方案缺少备选票选择')
                if category not in alternatives:
                    raise AlternativesAnalysisError('回算方案选择超出备选集合')
            else:
                category = vote['category']
            counts[categories.index(category)] += 1
            votes.append({
                'vote_id': vote['id'],
                'rater': rater,
                'category': category,
                'original_category': vote['category'],
                'was_candidate': bool(alternatives),
                'alternatives': list(alternatives) if alternatives else None,
            })
        if sum(counts) != RATERS_PER_SPECIMEN:
            raise AlternativesAnalysisError('回算方案每试样须恰3票')
        specimen_pair_sum = sum(value * (value - 1) for value in counts)
        pair_sum += specimen_pair_sum
        for index, value in enumerate(counts):
            totals[index] += value
        assignments.append({
            'specimen_id': specimen['id'],
            'reference': specimen['reference'],
            'description': specimen.get('description', ''),
            'counts': counts,
            'item_agreement': float(Fraction(
                specimen_pair_sum,
                RATERS_PER_SPECIMEN * (RATERS_PER_SPECIMEN - 1))),
            'votes': votes,
        })
    return assignments, totals, pair_sum


def _endpoint(name, ordered, raters, categories, lookup, chosen, N, C):
    assignments, totals, pair_sum = _replay_plan(
        ordered, raters, categories, lookup, chosen, C)
    total_votes = N * RATERS_PER_SPECIMEN
    total_square = sum(value * value for value in totals)
    denominator = (total_votes ** 2) - total_square
    if denominator <= 0:
        raise AlternativesAnalysisError('端点方案为全同类，κ未定义，不能作为有定义端点')
    pbar = Fraction(pair_sum, N * RATERS_PER_SPECIMEN * (RATERS_PER_SPECIMEN - 1))
    pe = Fraction(total_square, total_votes ** 2)
    kappa = (pbar - pe) / (1 - pe)
    return {
        'name': name,
        'kappa': float(kappa),
        'kappa_rational': _rational(kappa),
        'pbar': float(pbar),
        'pbar_rational': _rational(pbar),
        'pe': float(pe),
        'pe_rational': _rational(pe),
        'category_totals': totals,
        'category_prevalence': [value / total_votes for value in totals],
        'pair_sum_S': pair_sum,
        'total_square_T': total_square,
        'total_votes_squared': total_votes ** 2,
        'assignments': assignments,
        'recomputed_from_plan': {
            'pair_sum_S': pair_sum,
            'total_square_T': total_square,
            'kappa': float(kappa),
            'kappa_rational': _rational(kappa),
            'formula': FORMULA,
            'matches_bound': None,  # set by caller after comparison
        },
    }


def analyze_alternatives(study, specimens, votes, config,
                         deadline_seconds=DEFAULT_DEADLINE_SECONDS,
                         memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB):
    started = time.monotonic()
    categories, raters, category_index, ordered, lookup = _prepare(study, specimens, votes)
    C = len(categories)
    N = len(ordered)
    total_votes = N * RATERS_PER_SPECIMEN
    (definite_totals, fixed_pair_sum, affected, candidate_votes,
     legal_schemes) = _collect(
        categories, raters, category_index, ordered, lookup)
    if candidate_votes == 0:
        raise AlternativesAnalysisError('研究没有备选票，请使用原确定票分析')

    local = []
    for specimen, base, candidates in affected:
        local.append((specimen, base, candidates,
                      _local_options(base, candidates, C)))
    guards, state_count = _scale_guards(
        local, candidate_votes, C, memory_limit_mb, deadline_seconds, _rss_mb())

    states = []
    for used in range(candidate_votes + 1):
        states.extend(_compositions(used, C))
    index = {state: position for position, state in enumerate(states)}
    start = index[(0,) * C]
    current_min = {start: 0}
    current_max = {start: 0}
    min_parents = []
    max_parents = []
    transitions = 0
    for layer, (specimen, base, candidates, options) in enumerate(local):
        elapsed = time.monotonic() - started
        if elapsed > deadline_seconds:
            raise AlternativesRefused(
                f'精确计算超过{deadline_seconds:g}秒时限；已拒绝，未给出近似值',
                elapsed_seconds=elapsed, layer=layer)
        if _rss_mb() > memory_limit_mb - MEMORY_HEADROOM_MB:
            raise AlternativesRefused(
                f'精确计算驻留内存超过{memory_limit_mb}MB安全上限；已拒绝，未给出近似值',
                rss_mb=_rss_mb(), layer=layer)
        next_min = {}
        next_max = {}
        parent_min = {}
        parent_max = {}
        option_count = len(options)
        for previous, base_value in current_min.items():
            state = states[previous]
            for option_index, (addition, choice, pair_sum) in enumerate(options):
                target = index[tuple(state[j] + addition[j] for j in range(C))]
                transitions += 1
                candidate_min = base_value + pair_sum
                if target not in next_min or candidate_min < next_min[target]:
                    next_min[target] = candidate_min
                    parent_min[target] = previous * option_count + option_index
                candidate_max = current_max[previous] + pair_sum
                if target not in next_max or candidate_max > next_max[target]:
                    next_max[target] = candidate_max
                    parent_max[target] = previous * option_count + option_index
                if transitions % 65536 == 0:
                    elapsed = time.monotonic() - started
                    if elapsed > deadline_seconds:
                        raise AlternativesRefused(
                            f'精确计算超过{deadline_seconds:g}秒时限；已拒绝，未给出近似值',
                            elapsed_seconds=elapsed, layer=layer)
                    if transitions > MAX_TRANSITIONS:
                        raise AlternativesRefused(
                            f'精确计算超过{MAX_TRANSITIONS}次状态转移；已拒绝，未给出近似值',
                            transitions=transitions)
        current_min, current_max = next_min, next_max
        min_parents.append(parent_min)
        max_parents.append(parent_max)
    if transitions > MAX_TRANSITIONS:
        raise AlternativesRefused(
            f'精确计算超过{MAX_TRANSITIONS}次状态转移；已拒绝，未给出近似值',
            transitions=transitions)
    if _rss_mb() > memory_limit_mb - MEMORY_HEADROOM_MB:
        raise AlternativesRefused(
            f'精确计算驻留内存超过{memory_limit_mb}MB安全上限；已拒绝，未给出近似值',
            rss_mb=_rss_mb())

    limit = total_votes ** 2
    best_min = None
    best_max = None
    for position in current_min:
        state = states[position]
        total_square = sum((definite_totals[j] + state[j]) ** 2 for j in range(C))
        if total_square >= limit:
            continue
        denominator = 2 * (limit - total_square)
        numerator_min = 3 * N * (fixed_pair_sum + current_min[position]) - 2 * total_square
        exact_min = Fraction(numerator_min, denominator)
        if best_min is None or exact_min < best_min[0]:
            best_min = (exact_min, position)
        numerator_max = 3 * N * (fixed_pair_sum + current_max[position]) - 2 * total_square
        exact_max = Fraction(numerator_max, denominator)
        if best_max is None or exact_max > best_max[0]:
            best_max = (exact_max, position)

    undefined_categories = _undefined_categories(categories, raters, ordered, lookup)
    undefined_count = len(undefined_categories)
    defined_schemes = legal_schemes - undefined_count

    def replay(best, parents):
        if best is None:
            return None
        position = best[1]
        chosen = {}
        for layer in range(len(local) - 1, -1, -1):
            specimen, base, candidates, options = local[layer]
            packed = parents[layer][position]
            previous, option_index = divmod(packed, len(options))
            addition, choice, pair_sum = options[option_index]
            for (vote, allowed), category_choice in zip(candidates, choice):
                chosen[vote['id']] = categories[category_choice]
            position = previous
        return chosen

    result = {
        'analysis_mode': 'alternatives_exact',
        'method': 'exhaustive-dynamic-programme-over-category-counts',
        'exactness': 'exact rational arithmetic over every legal assignment; no sampling, no point estimate',
        'not_a_confidence_interval': True,
        'source_study': study,
        'categories': categories,
        'raters': raters,
        'specimen_count': N,
        'raters_per_specimen': RATERS_PER_SPECIMEN,
        'total_votes': total_votes,
        'candidate_vote_count': candidate_votes,
        'candidate_specimen_count': len(affected),
        'legal_scheme_count': str(legal_schemes),
        'defined_scheme_count': str(defined_schemes),
        'undefined_schemes': {
            'exists': undefined_count > 0,
            'count': undefined_count,
            'categories': undefined_categories,
            'reason': ('Pe=1：全部票落同一类别，κ未定义；这些方案不计入有定义κ的最小/最大值'
                       if undefined_count else
                       '不存在全部票同类的合法方案，所有合法方案的κ均有定义'),
        },
        'formula': FORMULA,
        'guards': {
            **guards,
            'transitions_visited': transitions,
            'elapsed_seconds': None,
            'rss_mb': None,
        },
        'fingerprint': fingerprint_alternatives(study, specimens, votes, config),
        'interpretation': ('本结果是全部合法定类方案中有定义κ的精确最小/最大值，不是抽样区间，'
                           '也不是重采样经验区间。备选票允许任一候选类别，确定票保持原票；'
                           '每个端点都给出可逐票回算的完整方案。'),
    }

    for name, best, parents in (('min', best_min, min_parents),
                                ('max', best_max, max_parents)):
        if best is None:
            result[name] = None
            continue
        chosen = replay(best, parents)
        endpoint = _endpoint(name, ordered, raters, categories, lookup, chosen, N, C)
        if (endpoint['kappa_rational']['numerator'] != best[0].numerator or
                endpoint['kappa_rational']['denominator'] != best[0].denominator):
            raise AlternativesAnalysisError('端点回算与动态规划结果不一致，拒绝输出')
        endpoint['recomputed_from_plan']['matches_bound'] = True
        result[name] = endpoint

    if result['min'] is None or result['max'] is None:
        result['range'] = None
        result['range_status'] = 'undefined_only'
        result['range_reason'] = '所有合法方案均为全同类（Pe=1），没有有定义的κ端点。'
    else:
        result['range'] = {
            'kappa_min': result['min']['kappa'],
            'kappa_max': result['max']['kappa'],
            'kappa_min_rational': result['min']['kappa_rational'],
            'kappa_max_rational': result['max']['kappa_rational'],
            'width': result['max']['kappa'] - result['min']['kappa'],
        }
        result['range_status'] = 'defined'
        result['range_reason'] = '在全部合法方案中排除Pe=1方案后，精确最小/最大值由端点方案回算确认。'
    result['guards']['elapsed_seconds'] = time.monotonic() - started
    result['guards']['rss_mb'] = _peak_rss_mb()
    return result


def verify_plan(study, specimens, votes, endpoint, assignments):
    """Recompute κ for a user-entered endpoint plan and check its legality.

    ``assignments`` maps vote ids to chosen categories.  Every vote must be
    present exactly once; definite votes must keep their recorded category and
    candidate votes must stay inside their allowed set.  The result is exact
    and independent of the stored run.
    """
    categories, raters, category_index, ordered, lookup = _prepare(study, specimens, votes)
    C = len(categories)
    N = len(ordered)
    known = {}
    for specimen in ordered:
        for rater in raters:
            vote = lookup[specimen['id']][rater]
            known[vote['id']] = vote
    if not isinstance(assignments, list):
        raise AlternativesAnalysisError('方案须为逐票列表')
    chosen = {}
    for item in assignments:
        if not isinstance(item, dict) or 'vote_id' not in item or 'category' not in item:
            raise AlternativesAnalysisError('逐票方案须含vote_id与category')
        vote_id = item['vote_id']
        if vote_id not in known:
            raise AlternativesAnalysisError(f'方案含不属于本研究的票{vote_id}')
        if vote_id in chosen:
            raise AlternativesAnalysisError(f'票{vote_id}重复出现')
        category = item['category']
        if category not in category_index:
            raise AlternativesAnalysisError(f'票{vote_id}的类别不在声明类别中')
        chosen[vote_id] = category
    missing = sorted(set(known) - set(chosen))
    if missing:
        raise AlternativesAnalysisError(f'方案缺少{len(missing)}票，无法完整回算')
    for vote_id, category in chosen.items():
        vote = known[vote_id]
        alternatives = vote.get('alternatives')
        if alternatives:
            if category not in alternatives:
                raise AlternativesAnalysisError(f'票{vote_id}选择超出备选集合')
        elif category != vote['category']:
            raise AlternativesAnalysisError(f'确定票{vote_id}必须保持原票类别')
    assignment_rows, totals, pair_sum = _replay_plan(
        ordered, raters, categories, lookup, chosen, C)
    total_votes = N * RATERS_PER_SPECIMEN
    total_square = sum(value * value for value in totals)
    if total_square >= total_votes ** 2:
        return {
            'legal': True,
            'defined': False,
            'reason': 'Pe=1：全部票落同一类别，κ未定义',
            'endpoint': endpoint,
            'category_totals': totals,
            'pair_sum_S': pair_sum,
            'total_square_T': total_square,
            'kappa': None,
            'kappa_rational': None,
            'matches_endpoint': False,
            'assignments': assignment_rows,
        }
    pbar = Fraction(pair_sum, N * RATERS_PER_SPECIMEN * (RATERS_PER_SPECIMEN - 1))
    pe = Fraction(total_square, total_votes ** 2)
    kappa = (pbar - pe) / (1 - pe)
    return {
        'legal': True,
        'defined': True,
        'reason': '方案逐票合法，κ由完整方案整数计数精确回算',
        'endpoint': endpoint,
        'kappa': float(kappa),
        'kappa_rational': _rational(kappa),
        'pbar': float(pbar),
        'pbar_rational': _rational(pbar),
        'pe': float(pe),
        'pe_rational': _rational(pe),
        'category_totals': totals,
        'pair_sum_S': pair_sum,
        'total_square_T': total_square,
        'matches_endpoint': None,  # filled by service against stored endpoints
        'assignments': assignment_rows,
    }
