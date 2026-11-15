from pydantic import BaseModel,Field,ConfigDict
from typing import Literal,Optional
class AlternativesPreflightInput(BaseModel):
 study_id:int=Field(gt=0)
class AlternativesRunInput(BaseModel):
 model_config=ConfigDict(str_strip_whitespace=True)
 study_id:int=Field(gt=0)
 name:str=Field(min_length=2,max_length=180)
class PlanVote(BaseModel):
 model_config=ConfigDict(str_strip_whitespace=True)
 vote_id:int=Field(gt=0)
 category:str=Field(min_length=1,max_length=80)
class PlanVerifyInput(BaseModel):
 model_config=ConfigDict(allow_inf_nan=False)
 endpoint:Literal['min','max','custom']
 assignments:list[PlanVote]=Field(min_length=1,max_length=720)
 note:Optional[str]=Field(default=None,max_length=2000)
