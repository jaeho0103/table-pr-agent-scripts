#!/usr/bin/env python3
"""
반다이남코코리아몰 건프라 신상품 모니터링
- 건프라 카테고리 페이지를 파싱하여 상품 목록을 가져옴
- 이전 목록과 비교하여 새 상품이 있으면 알림 텍스트 출력
- 상태 파일: /home/node/.openclaw/workspace/memory/bnkr-gunpla-state.json
"""

import re
import json
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://www.bnkrmall.co.kr/goods/category.do?"
    "cate=1576&page=1&cateName=%EA%B1%B4%ED%94%84%EB%9D%BC&endGoods=Y"
)
STATE_FILE = Path("/home/node/.openclaw/workspace/memory/bnkr-gunpla-state.json")
BASE = "https://www.bnkrmall.co.kr"


def fetch_product_status(gno):
    """watchlist 상품의 재고 상태를 상품 상세 페이지에서 직접 확인.
    판단 기준:
    - class="sold_out" 있으면 품절
    - class="end_reserv" 또는 class="type reservation end" 있으면 예약종료(구매불가)
    - 위 두 조건 모두 없으면 구매 가능
    """
    url = f"{BASE}/goods/detail.do?gno={gno}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # 상품명: hidden input goodsName
        name_m = re.search(r'name="goodsName"\s+value="([^"]+)"', html) \
              or re.search(r'<meta name="description"\s+content="([^"]+)"', html)
        name = name_m.group(1).strip() if name_m else gno
        # 품절: sold_out 클래스
        sold_out_class = bool(re.search(r'class="sold_out[^"]*"', html))
        # 예약종료: end_reserv 버튼 또는 reservation end 타입
        reservation_ended = bool(re.search(r'class="[^"]*end_reserv[^"]*"', html)) \
                         or bool(re.search(r'class="type reservation end"', html))
        sold_out = sold_out_class or reservation_ended
        # 가격: hidden input price
        price_m = re.search(r'name="price"\s+value="(\d+)"', html)
        price = f"{int(price_m.group(1)):,}" if price_m else ""
        return {"gno": gno, "name": name, "sold_out": sold_out,
                "price": price, "caption": "", "badge": "",
                "link": url}
    except Exception:
        return None


def fetch_products():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    products = []
    # Parse <li> blocks with gno links
    for m in re.finditer(
        r'<li\s+data-childno[^>]*>.*?</li>', html, re.DOTALL
    ):
        block = m.group()
        # Extract gno (product id)
        gno_m = re.search(r'gno=(\d+)', block)
        if not gno_m:
            continue
        gno = gno_m.group(1)

        # Extract caption (series name) if present
        caption_m = re.search(r'class="[^"]*caption[^"]*"[^>]*>([^<]+)', block)
        caption = caption_m.group(1).strip() if caption_m else ""

        # Extract product name from <h5>
        name_m = re.search(r'<h5[^>]*>([^<]+)', block)
        name = name_m.group(1).strip() if name_m else "unknown"

        # Extract price
        price_m = re.search(r'<span class="num[^"]*">\s*([\d,]+)', block)
        price = price_m.group(1).strip() if price_m else ""

        # Sold out?
        sold_out = "SOLD OUT" in block

        # Badge
        badge_m = re.search(r'class="[^"]*best[^"]*">([^<]+)', block)
        badge = badge_m.group(1).strip() if badge_m else ""

        link = f"{BASE}/goods/detail.do?gno={gno}"

        products.append({
            "gno": gno,
            "name": name,
            "caption": caption,
            "price": price,
            "sold_out": sold_out,
            "badge": badge,
            "link": link,
        })

    return products


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"known_gnos": [], "sold_out_status": {}, "watchlist": []}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    products = fetch_products()
    if not products:
        print("ERROR: No products parsed from page")
        sys.exit(1)

    state = load_state()
    known = set(state.get("known_gnos", []))

    new_products = [p for p in products if p["gno"] not in known]
    products_by_gno = {p["gno"]: p for p in products}

    prev_sold_out = state.get("sold_out_status", {})
    watchlist     = set(state.get("watchlist", []))

    # watchlist 중 카테고리 페이지에 없는 상품은 직접 상품 페이지에서 체크
    for gno in watchlist:
        if gno not in products_by_gno:
            p = fetch_product_status(gno)
            if p:
                products_by_gno[gno] = p

    # 재입고 감지: watchlist 중 이전에 품절이었다가 지금 구매 가능한 것
    restocked = []
    for gno in watchlist:
        p = products_by_gno.get(gno)
        if p and not p["sold_out"] and prev_sold_out.get(gno) is True:
            restocked.append(p)

    # 현재 품절 상태 저장 (watchlist + 신상품 대상)
    new_sold_out = dict(prev_sold_out)
    for p in products:
        if p["gno"] in watchlist or p["gno"] not in known:
            new_sold_out[p["gno"]] = p["sold_out"]

    # Update state
    all_gnos = list({p["gno"] for p in products} | known)
    save_state({"known_gnos": all_gnos, "sold_out_status": new_sold_out, "watchlist": list(watchlist)})

    if not known:
        print(f"INIT: Saved {len(products)} products as baseline. No alerts.")
        sys.exit(0)

    if not new_products and not restocked:
        print("NO_NEW")
        sys.exit(0)

    lines = []

    # 신상품 알림 (품절 포함 전체)
    if new_products:
        lines.append(f"🔔 반다이남코코리아몰 건프라 신상품 {len(new_products)}개!")
        for p in new_products:
            status = "❌품절" if p["sold_out"] else "✅구매가능"
            cap = f" ({p['caption']})" if p['caption'] else ""
            lines.append(f"\n• {p['name']}{cap}")
            lines.append(f"  💰 {p['price']}원 {status}")
            if p["badge"]:
                lines.append(f"  🏷️ {p['badge']}")
            lines.append(f"  🔗 {p['link']}")

    # 재입고 알림
    if restocked:
        if lines:
            lines.append("")
        lines.append(f"📦 재입고 알림 {len(restocked)}개!")
        for p in restocked:
            cap = f" ({p['caption']})" if p['caption'] else ""
            lines.append(f"\n• {p['name']}{cap}")
            lines.append(f"  💰 {p['price']}원 ✅구매가능")
            lines.append(f"  🔗 {p['link']}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
