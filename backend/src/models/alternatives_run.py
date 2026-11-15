from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import ForeignKey,String,JSON,Text,DateTime
from sqlalchemy.dialects.mysql import DOUBLE
from datetime import datetime,timezone
from src.config.database import Base
class AlternativesRun(Base):
 """精确备选票分析运行。

 与 AgreementRun 分开存放，因为它的结论是合法方案中有定义 κ 的精确最小值/
 最大值及两端逐票方案，不是单点 κ、也不是 bootstrap 区间。原票与确定票分析
 完全不受影响。"""
 __tablename__='alternatives_runs'
 id:Mapped[int]=mapped_column(primary_key=True)
 study_id:Mapped[int]=mapped_column(ForeignKey('agreement_studies.id'))
 name:Mapped[str]=mapped_column(String(180),unique=True)
 config:Mapped[dict]=mapped_column(JSON)
 status:Mapped[str]=mapped_column(String(24),default='queued')
 result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
 error:Mapped[str|None]=mapped_column(Text,nullable=True)
 kappa_min:Mapped[float|None]=mapped_column(DOUBLE(asdecimal=False),nullable=True)
 kappa_max:Mapped[float|None]=mapped_column(DOUBLE(asdecimal=False),nullable=True)
 created_by:Mapped[str]=mapped_column(String(120))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
