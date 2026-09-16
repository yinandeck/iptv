#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV M3U 去重脚本
- 按频道名分组，只保留画质最高的一条
- 画质优先级：4K > 极清 > 超清 > 高清 > 标清 > 未知
- 保持原作者顺序，不重新排序
- 可纠正分组（CCTV 统一归央视热播）
- 在大湾区卫视后面插入「香港卫视」
- 额外生成一份回看版 clean-replay.m3u
"""

import re
import urllib.request
from datetime import datetime, timezone, timedelta

SOURCE_URL = "https://raw.githubusercontent.com/Healer-sys/Home/refs/heads/main/iptv/gx.m3u"
OUTPUT_FILE = "clean.m3u"
OUTPUT_REPLAY_FILE = "clean-replay.m3u"

# 回看反代 IP
REPLAY_IP = "39.137.139.50"

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

# ===== 要插入的固定频道 =====
INSERT_AFTER = "大湾区卫视"
INSERT_EXTINF = (
    '#EXTINF:-1 tvg-name="香港卫视" '
    'tvg-logo="" '
    'group-title="全国热播",香港卫视'
)
INSERT_URL = "http://cdnrrs.gx.chinamobile.com/PLTV/77777777/224/3221226321/index.m3u8?servicetype=1"
# ============================


def get_quality(name: str) -> int:
    m = QUALITY_SUFFIX.search(name)
    if m:
        key = m.group(1).lower()
        return QUALITY_RANK.get(key, 0)
    return 0


def get_base_name(name: str) -> str:
    return QUALITY_SUFFIX.sub("", name).strip()


def parse_m3u(text: str):
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
    m = re.search(r'tvg-name="([^"]*)"', extinf)
    if m:
        return m.group(1)
    m = re.search(r",(.+)$", extinf)
    return m.group(1).strip() if m else ""


def fix_group(extinf: str) -> str:
    tvg_name = extract_tvg_name(extinf)
    if re.match(r"^CCTV", tvg_name):
        extinf = re.sub(r'group-title="[^"]*"', 'group-title="央视热播"', extinf)
    return extinf


def insert_channel(entries):
    new_entries = []
    inserted = False
    for extinf, url in entries:
        new_entries.append((extinf, url))
        tvg_name = extract_tvg_name(extinf)
        base = get_base_name(tvg_name)
        if not inserted and base == INSERT_AFTER:
            new_entries.append((INSERT_EXTINF, INSERT_URL))
            inserted = True
    if not inserted:
        print(f"警告: 未找到「{INSERT_AFTER}」，香港卫视已追加到末尾")
        new_entries.append((INSERT_EXTINF, INSERT_URL))
    return new_entries


def to_replay_url(url: str) -> str:
    """把直播地址转成回看地址：
    - 前面加反代 IP
    - servicetype=1 改成 servicetype=3
    """
    if url.startswith("http://"):
        url = "http://" + REPLAY_IP + "/" + url[len("http://"):]
    elif url.startswith("https://"):
        url = "http://" + REPLAY_IP + "/" + url[len("https://"):]
    url = url.replace("servicetype=1", "servicetype=3")
    return url


def main():
    print(f"下载源: {SOURCE_URL}")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    entries = parse_m3u(raw)
    print(f"原始条目数: {len(entries)}")

    entries = [(fix_group(e), u) for e, u in entries]
    entries = insert_channel(entries)
    print(f"插入后条目数: {len(entries)}")

    best = {}
    order = []
    for extinf, url in entries:
        tvg_name = extract_tvg_name(extinf)
        base = get_base_name(tvg_name)
        quality = get_quality(tvg_name)

        if base not in best:
            order.append(base)
            best[base] = (quality, extinf, url, tvg_name)
        elif quality > best[base][0]:
            best[base] = (quality, extinf, url, tvg_name)

    print(f"去重后条目数: {len(best)}")

    bj_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST+0800")

    # 写直播版
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n')
        f.write(f'# update time: {bj_time}\n')
        for base in order:
            _, extinf, url, _ = best[base]
            f.write(extinf + "\n")
            f.write(url + "\n\n")
    print(f"已生成: {OUTPUT_FILE}")

    # 写回看版
    with open(OUTPUT_REPLAY_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n')
        f.write(f'# update time: {bj_time}\n')
        f.write('# 回看模式：servicetype=3 + 反代 IP\n')
        for base in order:
            _, extinf, url, _ = best[base]
            replay_url = to_replay_url(url)
            f.write(extinf + "\n")
            f.write(replay_url + "\n\n")
    print(f"已生成: {OUTPUT_REPLAY_FILE}")


if __name__ == "__main__":
    main()
