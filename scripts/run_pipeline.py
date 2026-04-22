"""
GM → Qlib 数据管道 CLI 入口

用法:
    uv run python scripts/run_pipeline.py --config configs/csi1000_qlib.yaml
    uv run python scripts/run_pipeline.py --pipeline csi1000_qlib --stages clean,ingest
"""
import sys
import argparse
import logging
import yaml
from pathlib import Path

# 添加 src 目录到 Python 路径
src_path = Path(__file__).resolve().parent.parent / "src"
if src_path not in sys.path:
    sys.path.insert(0, str(src_path))

from pipelines import get_pipeline


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Run data pipeline")
    parser.add_argument("--config", type=str, help="YAML config file path")
    parser.add_argument("--pipeline", type=str, help="Pipeline name (if no config)")
    parser.add_argument("--stages", type=str, help="Comma-separated stages to run")
    parser.add_argument("--exports-base", type=str, default="data/exports", help="Exports directory")
    parser.add_argument("--qlib-output", type=str, default="data/qlib_output", help="Qlib CSV output")
    parser.add_argument("--qlib-bin", type=str, default="data/qlib_bin", help="Qlib binary output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # 日志配置
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # 加载配置
    if args.config:
        config = load_config(args.config)
    elif args.pipeline:
        stages = args.stages.split(",") if args.stages else ["download", "validate", "clean", "ingest"]
        config = {
            "pipeline": {"name": args.pipeline, "stages": stages},
            "exports_base": args.exports_base,
            "qlib_output": args.qlib_output,
            "qlib_bin": args.qlib_bin
        }
    else:
        parser.error("Either --config or --pipeline must be provided")

    # 获取 Pipeline 类并实例化
    pipeline_name = config["pipeline"]["name"]
    pipeline_class = get_pipeline(pipeline_name)
    pipeline = pipeline_class(config)

    # 运行
    logging.info(f"Starting pipeline: {pipeline_name}")
    logging.info(f"Stages: {pipeline.stages}")
    pipeline.run()
    logging.info("Pipeline completed")


if __name__ == "__main__":
    main()