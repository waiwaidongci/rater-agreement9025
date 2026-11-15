def _valid_text(value,limit=80):
 return isinstance(value,str) and bool(value.strip()) and len(value)<=limit

def validate_candidates(study,votes):
 """Candidate votes must stay inside the declared category list and keep
 their original label among the allowed set.  The original definite label is
 never replaced; alternatives are additional information only."""
 categories=study['categories']
 for vote in votes:
  alternatives=vote.get('alternatives')
  if alternatives is None:continue
  if not isinstance(alternatives,list) or not 2<=len(alternatives)<=len(categories):raise ValueError('备选票须限定2..类别数以内的候选类别')
  if any(not _valid_text(c) or c not in categories for c in alternatives):raise ValueError('备选类别须来自预先声明类别')
  if len(set(alternatives))!=len(alternatives):raise ValueError('备选类别须唯一')
  if vote['category'] not in alternatives:raise ValueError('原票类别须属于该票的备选集合')

def validate_source(study,specimens,votes):
 categories=study['categories'];raters=study['raters']
 if not 2<=len(categories)<=6 or len(set(categories))!=len(categories) or any(not _valid_text(c) for c in categories):raise ValueError('类别须2..6个唯一非空声明，顺序固定')
 if len(raters)!=3 or len(set(raters))!=3 or any(not _valid_text(r) for r in raters):raise ValueError('须声明3位唯一固定标记者')
 if not 2<=len(specimens)<=240 or len({s['id'] for s in specimens})!=len(specimens) or len({s['reference'] for s in specimens})!=len(specimens):raise ValueError('须2..240个唯一试样')
 lookup={s['id']:[] for s in specimens}
 for v in votes:
  if v['specimen_id'] not in lookup or v['category'] not in categories or v['rater'] not in raters:raise ValueError('未知试样/类别/标记者')
  lookup[v['specimen_id']].append(v['rater'])
 for names in lookup.values():
  if len(names)!=3 or len(set(names))!=3 or set(names)!=set(raters):raise ValueError('每试样须同一固定3人面板各一票，不可缺票/重复')
 validate_candidates(study,votes)

def validate_config(config):
 b=config['bootstrap_repeats'];seed=config['seed']
 if type(b) is not int or not 400<=b<=1000 or type(seed) is not int or not 0<=seed<=1000000000 or config.get('panel_scope')!='fixed_three_raters':raise ValueError('B须400..1000，seed合法且固定三人面板')
