-- 002_alternatives.sql
-- 备选票精确边界分析。不修改既有票的原票类别：alternatives 只额外保存候选集合。
-- create_all 不会给既有表加列，升级既有数据库时执行本文件。

ALTER TABLE rater_votes ADD COLUMN alternatives JSON NULL;

-- 说明可关联确定票运行或备选票运行，二者恰一。
ALTER TABLE review_memos MODIFY COLUMN run_id INT NULL;
ALTER TABLE review_memos ADD COLUMN alternatives_run_id INT NULL;
ALTER TABLE review_memos ADD CONSTRAINT fk_review_memos_alternatives_run
  FOREIGN KEY (alternatives_run_id) REFERENCES alternatives_runs(id);

-- 精确边界运行：result 保存两端完整逐票方案，kappa_min/kappa_max 为有定义 κ 的
-- 精确端点（DOUBLE(asdecimal=False)，与既有 κ 列一致）。
CREATE TABLE IF NOT EXISTS alternatives_runs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  study_id INT NOT NULL,
  name VARCHAR(180) NOT NULL UNIQUE,
  config JSON NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'queued',
  result JSON NULL,
  error TEXT NULL,
  kappa_min DOUBLE NULL,
  kappa_max DOUBLE NULL,
  created_by VARCHAR(120) NOT NULL,
  created_at DATETIME NOT NULL,
  CONSTRAINT fk_alternatives_runs_study FOREIGN KEY (study_id) REFERENCES agreement_studies(id)
);
