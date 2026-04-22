# GM 数据增量下载模块设计

## 背景

当前 `scripts/download_gm.py` 已有部分增量逻辑（仅对 history 数据支持断点续传），但：
- 增量检测逻辑分散，不易复用
- `CSI1000QlibPipeline.download()` 为空实现
- Pipeline 和 CLI 无法共享下载逻辑

## 目标

设计独立模块 `src/data_download/`，实现：
1. **时间范围补全** — 检查已有数据最新日期，只下载缺失时间段
2. **标的补全** — 成分股变动后只下载新增标的
3. **Pipeline 集成** — download stage 可直接调用模块

## 设计决策

### 增量判断标准

采用**时间覆盖判断**：检查文件内最新数据日期，若已覆盖到请求的结束日期则跳过。

### 起点确定策略

采用**动态起点 + 动态终点**：
- 根据已有数据最新日期自动确定起点
- 无数据时使用配置的默认起点

### 架构方案

采用**完全重构**：创建独立模块，Pipeline 和 CLI 统一调用入口。

---

## 模块结构

```
src/data_download/
├── __init__.py              # 导出 CSI1000Downloader, IncrementalChecker
├── base.py                  # GMDownloader 抽象基类
├── incremental.py           # 增量检测逻辑
├── csi1000_downloader.py    # CSI1000Downloader 特化实现
└── gm_api.py                # GM API 封装（RateLimiter, fetcher 工厂）
```

### 职责划分

| 文件 | 职责 |
|------|------|
| `base.py` | 定义下载流程骨架，子类实现 `get_target_pool()` 和 `get_categories()` |
| `incremental.py` | 提供 `check_time_coverage()` 和 `check_symbol_coverage()` |
| `csi1000_downloader.py` | 继承基类，实现 CSI 1000 特定逻辑 |
| `gm_api.py` | 封装 GM SDK 调用，流控和重试装饰器 |

---

## 增量检测逻辑

```python
# src/data_download/incremental.py

@dataclass
class CoverageResult:
    covered: bool       # 是否已覆盖
    last_date: datetime # 已有数据最新日期
    gap_start: datetime # 缺口起始日期

@dataclass
class SymbolGap:
    existing: set       # 已有标的
    missing: list       # 缺失标的

def check_time_coverage(file_path: Path, end_date: datetime) -> CoverageResult:
    """
    检查文件内数据是否已覆盖到请求的结束日期
    """
    # 读取文件最后一行的时间戳
    # 如果 last_date >= end_date，返回 covered=True
    # 否则返回 covered=False, gap_start=last_date + 1秒

def check_symbol_coverage(category_dir: Path, target_pool: list) -> SymbolGap:
    """
    检查目录下缺失的标的
    """
    # 扫描目录下已有文件
    # 对比 target_pool，返回缺失标的列表
```

**使用方式**：
1. 每个 category 下载前调用 `check_symbol_coverage()` 确定缺失标的
2. 对已有标的调用 `check_time_coverage()` 确定时间缺口
3. 只下载缺失部分，跳过已覆盖的

---

## CSI1000Downloader 类

```python
# src/data_download/csi1000_downloader.py

class CSI1000Downloader(GMDownloader):
    """CSI 1000 指数数据下载器"""

    def __init__(self, config: dict):
        self.index_code = config.get("index_code", "SHSE.000852")
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.start_date = config.get("start_date")  # 配置的默认起点
        self.end_date = config.get("end_date")      # 动态终点

    def get_target_pool(self) -> list:
        """从 GM API 获取成分股列表"""

    def get_categories(self) -> dict:
        """返回各数据类别的配置"""

    def download_category(self, category: str, fetch_func, fields=None):
        """执行单个类别的增量下载"""
        # 1. check_symbol_coverage() -> 确定缺失标的
        # 2. 对已有标的 check_time_coverage() -> 确定时间缺口
        # 3. 只下载缺失部分
        # 4. 合并新数据到已有文件

    def run(self):
        """执行完整下载流程"""
```

**Pipeline 集成**：
- `CSI1000QlibPipeline.download()` 直接调用 `CSI1000Downloader(config).run()`
- CLI 入口也调用同一类

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 单个标的下载失败 | 记录日志，继续处理其他标的，汇总报告 |
| GM API 调用超时 | 重试 3 次（指数退避），最终失败则跳过 |
| 成分股获取失败 | 效果流程终止，报告严重错误 |
| 文件写入失败 | 保留已下载数据在内存，报告错误 |

**日志输出**：
- INFO：下载进度、覆盖情况
- WARNING：单个标的失败
- ERROR：严重错误
- 最终汇总报告

---

## 测试策略

| 测试类型 | 测试内容 |
|----------|----------|
| 单元测试 | `incremental.py` 时间/标的覆盖检测 |
| 单元测试 | `gm_api.py` RateLimiter、fetcher |
| 集成测试 | `CSI1000Downloader` 完整流程（mock API） |
| 手动验证 | 小范围真实下载验证增量逻辑 |

**关键测试用例**：
- `test_check_time_coverage()`: 文件不存在、已覆盖、有缺口
- `test_check_symbol_coverage()`: 目录不存在、部分缺失、全部缺失
- `test_download_category_incremental()`: 验证只下载缺失部分