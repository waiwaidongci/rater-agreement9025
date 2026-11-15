from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import ForeignKey,String,JSON,UniqueConstraint
from src.config.database import Base
class RaterVote(Base):
 __tablename__='rater_votes'
 __table_args__=(UniqueConstraint('specimen_id','rater'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 specimen_id:Mapped[int]=mapped_column(ForeignKey('specimens.id'))
 rater:Mapped[str]=mapped_column(String(80))
 category:Mapped[str]=mapped_column(String(80))
 # 备选票：原票类别 category 保留，另限定该票可取的候选类别集合。
 alternatives:Mapped[list|None]=mapped_column(JSON,nullable=True)
