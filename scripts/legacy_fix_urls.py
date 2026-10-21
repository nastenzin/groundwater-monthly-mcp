# -*- coding: utf-8 -*-
"""Fix detail_url values in data/legacy_index.json using the verified xxzx article URLs."""
import json
from pathlib import Path

INDEX = Path("data/legacy_index.json")

DETAIL = {
    "2024-01": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202403/t20240328_1737669.html",
    "2024-02": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202404/t20240430_1745368.html",
    "2024-03": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202405/t20240522_1747512.html",
    "2024-04": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202406/t20240627_1753800.html",
    "2024-05": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202407/t20240731_1759785.html",
    "2024-06": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202408/t20240821_1767321.html",
    "2024-07": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202409/t20240912_1769669.html",
    "2024-08": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202410/t20241022_1775328.html",
    "2024-09": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202411/t20241122_1779876.html",
}

if __name__ == "__main__":
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    for r in idx:
        if r["period"] in DETAIL:
            r["detail_url"] = DETAIL[r["period"]]
    idx.sort(key=lambda r: r["period"])
    INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in idx:
        print(r["period"], "|", r["detail_url"])
