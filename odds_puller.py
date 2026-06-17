"""
中国体育彩票竞彩足球赔率拉取工具
用法: python D:/odds/odds_puller.py
输出: D:/odds/latest.json
"""

import requests
import json
import re
import os
from datetime import datetime

# ── 配置 ──────────────────────────────
OUTPUT_DIR = r"D:\odds"
OUTPUT_FILE = "latest.json"
MATCH_LIST_URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchListV1.qry?clientCode=3001"
CALCULATOR_URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=hhad,had,hafu,ttg,crs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.sporttery.cn/",
    "Origin": "https://www.sporttery.cn",
}

# ── 工具函数 ──────────────────────────

def safe_float(value, default=None):
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def clean_name(name):
    """清洗队名中的乱码后缀"""
    if not name:
        return name
    # 去掉括号内的非中文内容（通常是乱码英文缩写）
    name = re.sub(r'\(.*?\)', '', name)
    return name.strip()


def fetch_json(url, headers=None, timeout=15):
    """拉取 JSON，先尝试 UTF-8，失败则尝试 GBK"""
    h = HEADERS.copy()
    if headers:
        h.update(headers)

    r = requests.get(url, headers=h, timeout=timeout)

    # 尝试多种编码
    for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try:
            text = r.content.decode(encoding)
            return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    # 最后尝试
    return r.json()


def parse_match_list(data):
    """解析 getMatchListV1 返回的比赛列表"""
    if not data.get("success"):
        return [], f"API error: {data.get('errorCode')} - {data.get('errorMessage')}"

    matches = []
    for group in data.get("value", {}).get("matchInfoList", []):
        biz_date = group.get("businessDate", "")
        for sub in group.get("subMatchList", []):
            had = {}
            hhad = {}
            hafu_raw = ""
            ttg_raw = ""
            crs_raw = ""

            for odds in sub.get("oddsList", []):
                pool = odds.get("poolCode", "")
                if pool == "HAD":
                    had = {
                        "h": safe_float(odds.get("h")),
                        "d": safe_float(odds.get("d")),
                        "a": safe_float(odds.get("a")),
                    }
                elif pool == "HHAD":
                    hhad = {
                        "goalLine": safe_float(odds.get("goalLine")),
                        "h": safe_float(odds.get("h")),
                        "d": safe_float(odds.get("d")),
                        "a": safe_float(odds.get("a")),
                    }
                elif pool == "HAFU":
                    hafu_raw = odds.get("odds", "")
                elif pool == "TTG":
                    ttg_raw = odds.get("odds", "")
                elif pool == "CRS":
                    crs_raw = odds.get("odds", "")

            match = {
                "num": sub.get("matchNumStr", ""),
                "id": sub.get("matchId", 0),
                "date": sub.get("matchDate", biz_date),
                "time": sub.get("matchTime", ""),
                "league": sub.get("leagueAllName", ""),
                "home": clean_name(sub.get("homeTeamAllName", "")),
                "away": clean_name(sub.get("awayTeamAllName", "")),
                "status": sub.get("matchStatus", ""),
                "had": had,
                "hhad": hhad,
                "ttg_raw": ttg_raw,
                "hafu_raw": hafu_raw,
                "crs_raw": crs_raw,
            }
            matches.append(match)

    return matches, None


def parse_calculator(data):
    """解析 getMatchCalculatorV1 返回的详细赔率（含半全场、总进球）"""
    if not data.get("success"):
        return {}, f"Calculator error: {data.get('errorCode')}"

    result = {}
    for group in data.get("value", {}).get("matchInfoList", []):
        for sub in group.get("subMatchList", []):
            mid = sub.get("matchId", 0)

            had = sub.get("had", {})
            hhad = sub.get("hhad", {})
            hafu = sub.get("hafu", {})
            ttg = sub.get("ttg", {})

            info = {}

            if had:
                info["had"] = {
                    "h": safe_float(had.get("h")),
                    "d": safe_float(had.get("d")),
                    "a": safe_float(had.get("a")),
                }
            if hhad:
                info["hhad"] = {
                    "goalLine": safe_float(hhad.get("goalLine")),
                    "h": safe_float(hhad.get("h")),
                    "d": safe_float(hhad.get("d")),
                    "a": safe_float(hhad.get("a")),
                }
            if hafu:
                # 半全场返回字段可能是 hh/hd/ha/dh/dd/da/ah/ad/aa
                info["hafu"] = {
                    "胜胜": safe_float(hafu.get("hh")),
                    "胜平": safe_float(hafu.get("hd")),
                    "胜负": safe_float(hafu.get("ha")),
                    "平胜": safe_float(hafu.get("dh")),
                    "平平": safe_float(hafu.get("dd")),
                    "平负": safe_float(hafu.get("da")),
                    "负胜": safe_float(hafu.get("ah")),
                    "负平": safe_float(hafu.get("ad")),
                    "负负": safe_float(hafu.get("aa")),
                }
            if ttg:
                info["ttg"] = {
                    "0球": safe_float(ttg.get("s0")),
                    "1球": safe_float(ttg.get("s1")),
                    "2球": safe_float(ttg.get("s2")),
                    "3球": safe_float(ttg.get("s3")),
                    "4球": safe_float(ttg.get("s4")),
                    "5球": safe_float(ttg.get("s5")),
                    "6球": safe_float(ttg.get("s6")),
                    "7+球": safe_float(ttg.get("s7")),
                }

            result[mid] = info

    return result, None


def format_display(matches):
    """生成可读文本，世界杯全量，其余折叠"""
    wc = [m for m in matches if "世界杯" in m.get("league", "")]
    other = [m for m in matches if "世界杯" not in m.get("league", "")]

    lines = []
    lines.append("=" * 60)
    lines.append(f"竞彩足球赔率 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"共 {len(matches)} 场（世界杯 {len(wc)} 场 + 其他 {len(other)} 场）")
    lines.append("=" * 60)

    # 世界杯：全量展开
    lines.append(f"\n{'─' * 60}")
    lines.append(f"  🌍 世界杯 ({len(wc)} 场)")
    lines.append(f"{'─' * 60}")
    for m in wc:
        lines.append(f"\n## {m['num']} {m['home']} vs {m['away']} {m['date']} {m['time']}")
        lines.append(f"状态: {m['status']}")

        if m.get("had"):
            h = m["had"]
            lines.append(f"全场胜平负: {h['h']}/{h['d']}/{h['a']}")

        if m.get("hhad") and m["hhad"].get("h"):
            hh = m["hhad"]
            lines.append(f"让球({hh['goalLine']:+.0f}): {hh['h']}/{hh['d']}/{hh['a']}")

        if m.get("ttg_raw"):
            lines.append(f"总进球: {m['ttg_raw']}")

        if m.get("hafu_raw"):
            lines.append(f"半全场: {m['hafu_raw']}")

    # 其余联赛：折叠为一行
    if other:
        lines.append(f"\n{'─' * 60}")
        lines.append(f"  📁 其他联赛 ({len(other)} 场，折叠)")
        lines.append(f"{'─' * 60}")
        for m in other:
            had_str = ""
            if m.get("had"):
                h = m["had"]
                had_str = f" [{h['h']}/{h['d']}/{h['a']}]"
            lines.append(f"  {m['num']} {m['league']} {m['home']} vs {m['away']} {m['time']}{had_str}")

    return "\n".join(lines)


# ── 主流程 ────────────────────────────

def main():
    import sys
    # 强制 UTF-8 输出，避免 GBK 终端吞 emoji
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("═" * 50)
    print("  中国体育彩票 竞彩足球 赔率拉取")
    print("═" * 50)

    # 1. 拉取比赛列表（含胜平负 + 让球）
    print("\n[1/2] 拉取比赛列表...")
    data1 = fetch_json(MATCH_LIST_URL)
    matches, err = parse_match_list(data1)

    if err:
        print(f"  ❌ 比赛列表拉取失败: {err}")
        return

    print(f"  ✅ 获取 {len(matches)} 场比赛")

    # 2. 尝试拉取详细赔率（半全场、总进球）
    print("[2/2] 拉取详细赔率（半全场/总进球）...")
    calc_info = {}
    try:
        data2 = fetch_json(CALCULATOR_URL)
        calc_info, calc_err = parse_calculator(data2)
        if calc_err:
            print(f"  ⚠️ 详细赔率不可用: {calc_err}")
            print(f"  💡 如果你在国内，可能是IP或网络问题")
        else:
            # 合并到 matches
            enriched = 0
            for m in matches:
                mid = m["id"]
                if mid in calc_info:
                    ci = calc_info[mid]
                    if "hafu" in ci:
                        m["hafu"] = ci["hafu"]
                    if "ttg" in ci:
                        m["ttg"] = ci["ttg"]
                    enriched += 1
            print(f"  ✅ 为 {enriched} 场比赛补充了详细赔率")
    except Exception as e:
        print(f"  ⚠️ 详细赔率拉取失败: {e}")

    # 3. 保存
    output = {
        "fetched_at": datetime.now().isoformat(),
        "match_count": len(matches),
        "matches": matches,
    }

    # JSON 文件
    json_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  📁 JSON: {json_path}")

    # 可读文本
    txt_path = os.path.join(OUTPUT_DIR, "latest.txt")
    text = format_display(matches)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  📁 文本: {txt_path}")

    # 4. 打印预览（世界杯全量 + 其他折叠）
    wc = [m for m in matches if "世界杯" in m.get("league", "")]
    other = [m for m in matches if "世界杯" not in m.get("league", "")]

    print(f"\n{'─' * 50}")
    print(f"  🌍 世界杯 ({len(wc)} 场)")
    print(f"{'─' * 50}")

    for m in wc:
        had_str = ""
        if m.get("had"):
            had_str = f" 胜平负: {m['had']['h']}/{m['had']['d']}/{m['had']['a']}"

        hhad_str = ""
        if m.get("hhad") and m["hhad"].get("h"):
            hh = m["hhad"]
            hhad_str = f"  让球({hh['goalLine']:+.0f}): {hh['h']}/{hh['d']}/{hh['a']}"

        print(f"\n{m['num']} {m['home']} vs {m['away']} {m['time']}")
        print(f"{had_str}{hhad_str}")

        if m.get("ttg"):
            ttg = m["ttg"]
            vals = [f"{k}:{v}" for k, v in ttg.items() if v]
            print(f"  总进球: {', '.join(vals)}")

        if m.get("hafu"):
            hafu = m["hafu"]
            vals = [f"{k}:{v}" for k, v in hafu.items() if v]
            print(f"  半全场: {', '.join(vals)}")

    if other:
        print(f"\n{'─' * 50}")
        print(f"  📁 其他联赛 ({len(other)} 场，折叠)")
        print(f"{'─' * 50}")
        for m in other:
            had_str = ""
            if m.get("had"):
                h = m["had"]
                had_str = f" [{h['h']}/{h['d']}/{h['a']}]"
            print(f"  {m['num']} {m['league'][:6]} {m['home'][:6]} vs {m['away'][:6]} {m['time']}{had_str}")

    print(f"\n✅ 完成！共 {len(matches)} 场比赛")


if __name__ == "__main__":
    main()
