#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV M3U 去重脚本
- 按频道名分组，只保留画质最高的一条
- 画质优先级：4K > 极清 > 超清 > 高清 > 标清 > 未知
"""

import re
import urllib.request
from datetime import datetime, timezone, timedelta

SOURCE_URL = "https://raw.githubusercontent.com/Healer-sys/Home/refs/heads/main/iptv/gx.m3u"
OUTPUT_FILE = "clean.m3u"

# 画质优先级，数字越大越优先
QUALITY_RANK = {
    "4k": 100,
    "极清": 90,
    "超清": 80,
    "高清": 70,
    "标清": 60,
}

# 去掉画质后缀，得到频道“基名”
QUALITY_SUFFIX = re.compile(r"\s*(4K|极清|超清|高清|标清)\s*$", re.IGNORECASE)


def get_quality(name: str) -> int:
    """从频道名中提取画质等级"""
    m = QUALITY_SUFFIX.search(name)
    if m:
        key = m.group(1).lower()
        return QUALITY_RANK.get(key, 0)
    return 0


def get_base_name(name: str) -> str:
    """去掉画质后缀，得到频道基名，用于分组"""
    return QUALITY_SUFFIX.sub("", name).strip()


def parse_m3u(text: str):
    """解析 m3u，返回 [(extinf行, url行), ...]"""
    lines = [l.rstrip("\n") for l in text.splitlines()]
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            extinf = line
            url = ""
            j = i + 1
            while j < len(lines):
                if lines[j].startswith("#"):
                    j += 1
                    continue
                url = lines[j]
                break
            entries.append((extinf, url))
            i = j + 1
        else:
            i += 1
    return entries


def extract_tvg_name(extinf: str) -> str:
    """从 #EXTINF 行中提取 tvg-name"""
    m = re.search(r'tvg-name="([^"]*)"', extinf)
    if m:
        return m.group(1)
    # 没有 tvg-name 就用逗号后面的显示名
    m = re.search(r",(.+)$", extinf)
    return m.group(1).strip() if m else ""


def natural_key(name: str):
    """把名字里的数字按数值排序，例如 CCTV-2 排在 CCTV-10 前面"""
    parts = re.split(r'(\d+)', name)
    key = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p)))      # 数字按数值比
        else:
            key.append((1, p.lower()))   # 文字按字母比
    return key


def main():
    print(f"下载源: {SOURCE_URL}")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    entries = parse_m3u(raw)
    print(f"原始条目数: {len(entries)}")

    # 按频道基名分组，保留画质最高的
    best = {}
    for extinf, url in entries:
        tvg_name = extract_tvg_name(extinf)
        base = get_base_name(tvg_name)
        quality = get_quality(tvg_name)

        if base not in best or quality > best[base][0]:
            best[base] = (quality, extinf, url, tvg_name)

    print(f"去重后条目数: {len(best)}")

    # 北京时间
    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST+0800")

    # 写输出
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n')
        f.write(f'# update time: {bj_time}\n')
        for base in sorted(best.keys(), key=natural_key):
            _, extinf, url, _ = best[base]
            f.write(extinf + "\n")
            f.write(url + "\n\n")

    print(f"已生成: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
