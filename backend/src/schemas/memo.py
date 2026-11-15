from pydantic import BaseModel,Field,model_validator
from typing import Literal,Optional
class MemoInput(BaseModel):
 run_id:Optional[int]=Field(default=None,gt=0)
 alternatives_run_id:Optional[int]=Field(default=None,gt=0)
 name:str=Field(min_length=2,max_length=180)
 interpretation:str=Field(min_length=5,max_length=4000)
 next_step:str=Field(min_length=5,max_length=4000)
 @model_validator(mode='after')
 def exactly_one_source(self):
  if (self.run_id is None)==(self.alternatives_run_id is None):raise ValueError('说明须且只须关联一个完成运行（确定票或备选票）')
  return self
class ApprovalInput(BaseModel):
 status:Literal['approved','rejected']
 review_note:str=Field(min_length=2,max_length=2000)
