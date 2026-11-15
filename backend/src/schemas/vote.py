from pydantic import BaseModel,Field,ConfigDict
from typing import Optional
class VoteInput(BaseModel):
 model_config=ConfigDict(str_strip_whitespace=True)
 rater:str=Field(min_length=1,max_length=80)
 category:str=Field(min_length=1,max_length=80)
 alternatives:Optional[list[str]]=Field(default=None,max_length=6)
class VotePatch(BaseModel):
 model_config=ConfigDict(str_strip_whitespace=True)
 category:Optional[str]=Field(default=None,min_length=1,max_length=80)
 alternatives:Optional[list[str]]=Field(default=None,max_length=6)
