import hashlib,json
VERSION='fixed-panel-fleiss-row-bootstrap-v1'
def fingerprint(study,specimens,votes,config):
 # 确定票分析只消费原票类别；备选集合是另一条分析线的信息，不进该指纹，
 # 这样声明或修订备选集合不会改动既有确定票分析的冻结指纹。
 definite=[{k:v for k,v in vote.items() if k!='alternatives'} for vote in votes]
 payload={'version':VERSION,'study':study,'specimens':sorted(specimens,key=lambda s:s['reference']),'votes':sorted(definite,key=lambda v:(v['specimen_id'],v['rater'])),'config':config}
 return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
