# -*- coding: utf-8 -*-
"""
素材卡校验器（check_cards.py）
用途：校验《素材卡契约 v1》规定的素材卡格式，供"毛选决策方法论提炼工程"总集成阶段使用。

用法：
    python check_cards.py                # 扫描默认目录 提炼素材\
    python check_cards.py 提炼素材\第一卷  # 扫描指定目录
    python check_cards.py 某张卡.md        # 校验单个文件

规则来源：_协调/素材卡契约.md
退出码：全部 PASS 为 0，存在 FAIL 为 1。
仅使用 Python 3 标准库。
"""

import os
import re
import sys
import io

# Windows 控制台默认 GBK，强制 stdout 用 UTF-8，避免中文输出乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---- 契约常量 ----------------------------------------------------------

# 契约允许的全部决策场景标签
ALLOWED_SCENES = {
    "认知判断", "时机判断", "力量配置", "强弱转化", "矛盾分析", "组织决策",
    "调查研究", "路线选择", "谈判博弈", "执行方法", "战略定力", "风险控制",
}

# frontmatter 必备字段
REQUIRED_FIELDS = ["篇目", "卷", "年份", "决策场景", "一号线索", "金句"]

# 正文必备小节（二级标题）
REQUIRED_SECTIONS = ["方法论内核", "决策算法", "适用条件", "误用警示"]

# 正文总字数（不含 frontmatter）允许区间
MIN_CHARS, MAX_CHARS = 300, 800

# 决策算法步骤数允许区间
MIN_STEPS, MAX_STEPS = 3, 7

DEFAULT_SCAN_DIR = "提炼素材"


# ---- 工具函数 ----------------------------------------------------------

def count_cjk(text):
    """统计中日韩表意字符数（用于字数判定，与契约"字数"口径一致）。"""
    return sum(1 for ch in text if "一" <= ch <= "鿿")


def parse_card(path):
    """解析一张素材卡，返回 (fields, sections, body, err)。
    fields: frontmatter 键值 dict；sections: 二级标题->正文 dict；
    body: 不含 frontmatter 的正文文本；err: 结构级致命错误（无则 None）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        return None, None, None, "文件不是 UTF-8 编码"

    m = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", text, re.S)
    if not m:
        return None, None, None, "缺少 frontmatter（文件须以 --- 开头并以 --- 收尾）"
    fm_raw, body = m.group(1), text[m.end():]

    fields = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()

    sections = {}
    current = None
    buf = []
    for line in body.splitlines():
        hm = re.match(r"^##\s+(.*?)\s*$", line)
        if hm:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = hm.group(1), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()

    return fields, sections, body, None


def check_card(path):
    """校验单卡，返回问题列表（空列表 = PASS）。"""
    problems = []
    fields, sections, body, err = parse_card(path)
    if err:
        return [err]

    # 1. frontmatter 字段齐全且非空
    for f in REQUIRED_FIELDS:
        if f not in fields:
            problems.append("frontmatter 缺字段「%s」" % f)
        elif not fields[f]:
            problems.append("frontmatter 字段「%s」为空" % f)

    # 2. 决策场景标签合法：1–3 个、以 | 分隔、均在允许集合内
    if "决策场景" in fields and fields["决策场景"]:
        raw = fields["决策场景"]
        if "[" in raw or "," in raw or "，" in raw:
            problems.append("决策场景须用 | 分隔（疑似列表/逗号格式：%r）" % raw)
        tags = [t.strip() for t in raw.split("|") if t.strip()]
        bad = [t for t in tags if t not in ALLOWED_SCENES]
        if bad:
            problems.append("决策场景含非法标签：%s" % "、".join(bad))
        if not (1 <= len(tags) <= 3):
            problems.append("决策场景标签数须为 1–3 个，实际 %d 个" % len(tags))

    # 3. 年份为数字
    if "年份" in fields and fields["年份"] and not fields["年份"].isdigit():
        problems.append("年份应为数字，实际为 %r" % fields["年份"])

    # 4. 正文必备小节齐全
    for s in REQUIRED_SECTIONS:
        if s not in sections:
            problems.append("正文缺小节「## %s」" % s)
        elif not sections[s]:
            problems.append("小节「%s」内容为空" % s)

    # 5. 决策算法为 3–7 步有序列表
    if sections and sections.get("决策算法"):
        steps = re.findall(r"^\s*\d+[.、]\s*\S", sections["决策算法"], re.M)
        bullets = re.findall(r"^\s*[-*]\s*\S", sections["决策算法"], re.M)
        if bullets and not steps:
            problems.append("决策算法须用有序列表（1. 2. 3.），疑似用了无序列表")
        elif not (MIN_STEPS <= len(steps) <= MAX_STEPS):
            problems.append("决策算法步骤数须为 %d–%d 步，实际 %d 步" % (MIN_STEPS, MAX_STEPS, len(steps)))

    # 6. 总字数 300–800（按汉字计）
    n = count_cjk(body or "")
    if not (MIN_CHARS <= n <= MAX_CHARS):
        problems.append("正文字数须在 %d–%d 字，实际 %d 字" % (MIN_CHARS, MAX_CHARS, n))

    return problems


def iter_card_files(target):
    """产出目标下全部素材卡路径：递归 .md，排除以 _ 开头的文件（契约约定）。"""
    if os.path.isfile(target):
        yield target
        return
    for root, _dirs, files in os.walk(target):
        for name in sorted(files):
            if name.endswith(".md") and not name.startswith("_"):
                yield os.path.join(root, name)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCAN_DIR
    if not os.path.exists(target):
        print("错误：路径不存在：%s" % target)
        return 1

    files = list(iter_card_files(target))
    if not files:
        print("未找到素材卡（%s 下无符合条件的 .md）" % target)
        return 1

    n_pass = n_fail = 0
    for path in files:
        problems = check_card(path)
        if problems:
            n_fail += 1
            print("FAIL %s" % path)
            for p in problems:
                print("     - %s" % p)
        else:
            n_pass += 1
            print("PASS %s" % path)

    print("-" * 60)
    print("共 %d 张卡：PASS %d，FAIL %d" % (len(files), n_pass, n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
