#!/usr/bin/env python3
"""
Test Runner - 测试运行器
运行所有测试用例并生成报告
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
TEST_DIR = PROJECT_ROOT / "tests"
REPORT_DIR = PROJECT_ROOT / "test_reports"


def run_tests(verbose: bool = True, report_format: str = "text") -> dict:
    """运行所有测试用例"""
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(TEST_DIR),
        "-v" if verbose else "-q",
    ]
    
    if report_format == "json":
        cmd.extend(["--json-report", f"--json-report-file={REPORT_DIR}/report.json"])
    elif report_format == "html":
        cmd.extend(["--html=report.html", "--self-contained-html"])
    
    print(f"Running tests: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    """主函数"""
    print("🧪 Test Runner - 测试运行器")
    print("=" * 60)
    
    # 创建报告目录
    REPORT_DIR.mkdir(exist_ok=True)
    
    # 运行测试
    result = run_tests(verbose=True)
    
    # 打印结果
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print("=" * 60)
    print(result["stdout"])
    
    if result["stderr"]:
        print("\n⚠️  Warnings/Errors:")
        print(result["stderr"])
    
    # 返回测试结果
    if result["returncode"] == 0:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())