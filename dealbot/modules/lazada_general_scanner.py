"""Module Lazada General Scanner (Radar Săn Kèo Sập Sàn Toàn Sàn):
Quét tổng quát đa ngành hàng trên Lazada (LazMall / Tmall Global):
1. Không bó hẹp vào một ngách bàn phím, mở rộng sang Thiết bị điện tử, Gia dụng thông minh, Thời trang thể thao Tmall.
2. Săn lùng các deal giảm thẳng sâu đột xuất (Clearance / Glitch / Single-SKU Drop >= 50% - 85%).
3. Bộ lọc chống bẫy phụ kiện thông minh (loại trừ nắp bụi, cáp sạc, núm xoay, switch lẻ...).
4. Bắn Telegram cảnh báo trực tiếp và lưu vào DB lazada_deep_drops.
"""
import os, sys, time, json, re, unicodedata, random, threading
from typing import Dict, Any, List, Optional, Tuple
import db
from notify import tg
from . import lazada

# Danh mục quét mặc định đa ngành hàng mở rộng (Gaming, Phụ kiện Audio, Gia dụng thông minh, Thời trang Tmall)
# Danh mục quét mặc định đa ngành hàng mở rộng toàn diện (13 ngành chuẩn Lazada LazMall / Tmall, 20 từ khóa / ngành = 260 từ khóa)
DEFAULT_GENERAL_CATEGORIES = [
    {
        "id": "gaming",
        "name": "Thiết Bị Điện Tử & Gaming",
        "icon": "💻",
        "keywords": [
            "bàn phím cơ",
            "chuột gaming không dây",
            "tai nghe gaming 7.1",
            "tai nghe chụp tai bluetooth",
            "lót chuột cỡ lớn",
            "giá đỡ màn hình arm",
            "tay cầm chơi game không dây",
            "hub type c đa năng",
            "webcam máy tính 2k",
            "giá treo tai nghe",
            "màn hình gaming 144hz",
            "chuột công thái học",
            "bàn phím bluetooth không dây",
            "bàn phím cơ custom",
            "mic thu âm gaming",
            "ổ cứng di động ssd",
            "thẻ nhớ 128gb chính hãng",
            "quạt tản nhiệt laptop",
            "bộ phát wifi 6",
            "bút cảm ứng ipad"
        ]
    },
    {
        "id": "gadgets",
        "name": "Phụ Kiện Công Nghệ & Âm Thanh",
        "icon": "⚡",
        "keywords": [
            "củ sạc nhanh 65w gan",
            "củ sạc nhanh 100w",
            "củ sạc anker chính hãng",
            "pin sạc dự phòng 20000mah",
            "pin sạc dự phòng magsafe",
            "tai nghe bluetooth không dây tws",
            "tai nghe chống ồn anc",
            "loa bluetooth bass mạnh",
            "loa vi tính để bàn",
            "loa bluetooth mini chống nước",
            "loa thanh soundbar tivi",
            "cáp sạc nhanh 100w type c",
            "cáp sạc iphone chính hãng",
            "giá đỡ điện thoại để bàn",
            "đế sạc không dây 3 in 1",
            "tai nghe true wireless baseus",
            "tai nghe marshall chính hãng",
            "loa jbl chính hãng",
            "gimbal chống rung điện thoại",
            "thẻ nhớ sandisk 64gb"
        ]
    },
    {
        "id": "appliances",
        "name": "Gia Dụng Thông Minh & Điện Máy",
        "icon": "🍳",
        "keywords": [
            "nồi chiên không dầu điện tử",
            "robot hút bụi lau nhà",
            "máy hút bụi cầm tay không dây",
            "máy lọc không khí gia đình",
            "máy cạo râu đa năng",
            "bàn chải điện sóng âm",
            "máy tăm nước cầm tay",
            "tông đơ cắt tóc chuyên nghiệp",
            "máy sấy tóc ion âm",
            "quạt tích điện để bàn",
            "máy xay cầm tay mini",
            "nồi cơm điện cao tần",
            "bàn là hơi nước cầm tay",
            "máy ép chậm trái cây",
            "máy xay sinh tố đa năng",
            "ấm siêu tốc thủy tinh",
            "nồi lẩu nướng đa năng",
            "máy làm sữa hạt mini",
            "máy hút ẩm gia đình",
            "cân điện tử thông minh"
        ]
    },
    {
        "id": "fashion",
        "name": "Thời Trang & Thể Thao Tmall Global",
        "icon": "👟",
        "keywords": [
            "giày chạy bộ anta chính hãng",
            "giày bóng rổ li-ning",
            "giày xtep chính hãng",
            "giày thể thao peak taichi",
            "giày 361 chính hãng",
            "áo khoác gió thể thao nam",
            "áo thể thao thoáng khí",
            "quần jogger thể thao",
            "balo du lịch chống nước",
            "kính râm thể thao phân cực",
            "áo thun thể thao nam thấm hút",
            "quần short thể thao 2 lớp",
            "áo nỉ hoodie thể thao",
            "giày sneaker nam đế êm",
            "bình nước thể thao 1 lít",
            "găng tay tập gym",
            "thảm tập yoga tpe",
            "băng quấn khớp gối thể thao",
            "vợt cầu lông yonex chính hãng",
            "túi trống tập gym du lịch"
        ]
    },
    {
        "id": "beauty_skincare",
        "name": "Chăm Sóc Sắc Đẹp & Skincare",
        "icon": "🧴",
        "keywords": [
            "kem chống nắng kiềm dầu",
            "kem chống nắng anessa chính hãng",
            "serum b5 phục hồi da",
            "serum vitamin c sáng da",
            "nước tẩy trang loreal 400ml",
            "sữa rửa mặt cerave chính hãng",
            "kem dưỡng ẩm phục hồi la roche posay",
            "son môi kem lì black rouge",
            "son dưỡng môi trị thâm",
            "mặt nạ cấp ẩm phục hồi da",
            "nước hoa hồng toner không cồn",
            "tẩy tế bào chết da mặt",
            "dầu gội trị gàu giảm gãy rụng",
            "sữa tắm dưỡng ẩm thơm lâu",
            "kem dưỡng trắng da ban đêm",
            "kem mắt giảm quầng thâm bọng mắt",
            "máy triệt lông cầm tay mini",
            "máy rửa mặt sóng âm",
            "phấn nước cushion lâu trôi",
            "mascara chống nước cong mi"
        ]
    },
    {
        "id": "men_fashion",
        "name": "Thời Trang Nam Cao Cấp",
        "icon": "👔",
        "keywords": [
            "áo polo nam phối màu vải cá sấu",
            "áo polo nam form regular fit",
            "áo thun nam cổ tròn cotton 100%",
            "áo thun oversize nam basic",
            "áo sơ mi nam dài tay công sở",
            "áo sơ mi nam cộc tay đũi",
            "quần âu nam hàn quốc ống đứng",
            "quần tây nam co giãn cao cấp",
            "quần jean nam trơn dáng slim",
            "quần kaki nam ống suông",
            "quần short đũi nam thoáng mát",
            "áo khoác kaki nam bomber",
            "áo blazer nam phong cách hàn quốc",
            "thắt lưng nam da bò khóa tự động",
            "ví nam da bò mini gập gọn",
            "giày tây nam oxford derby",
            "giày lười nam da mềm",
            "giày chelsea boot nam",
            "tất vớ nam cổ ngắn cotton",
            "cà vạt nam bản nhỏ lịch lãm"
        ]
    },
    {
        "id": "women_fashion",
        "name": "Thời Trang Nữ & Phụ Kiện",
        "icon": "👗",
        "keywords": [
            "váy đầm dạ hội thiết kế sang trọng",
            "váy hoa nhí dáng xòe mùa hè",
            "đầm body dự tiệc quyến rũ",
            "áo kiểu nữ babydoll dễ thương",
            "áo croptop ôm body dài tay",
            "áo sơ mi nữ lụa cổ đức",
            "chân váy chữ a cạp cao",
            "chân váy xếp ly dáng dài",
            "quần ống rộng nữ cạp cao hack dáng",
            "quần jean ống loe nữ",
            "quần suông nữ chất tuyết mưa",
            "áo blazer nữ oversize hàn quốc",
            "áo khoác len cardigan nữ",
            "túi xách nữ đeo chéo kẹp nách",
            "túi tote vải canvas phong cách ulzzang",
            "balo nữ mini da pu đi học",
            "giày cao gót 5cm mũi nhọn",
            "giày búp bê mũi vuông đế mềm",
            "dép quai hậu nữ sandal đế bằng",
            "bộ đồ ngủ lụa satin cao cấp"
        ]
    },
    {
        "id": "mother_baby",
        "name": "Mẹ & Bé Chính Hãng",
        "icon": "👶",
        "keywords": [
            "bỉm tã dán bobby chính hãng",
            "tã quần moony tự nhiên",
            "tã quần huggies tràm trà",
            "sữa bột ensure gold chính hãng",
            "sữa nan optipro công thức",
            "sữa bột pediasure tăng chiều cao",
            "bình sữa hegen cổ rộng chính hãng",
            "bình sữa pigeon nội địa nhật",
            "máy hút sữa điện đôi không dây",
            "máy tiệt trùng sấy khô uvc bình sữa",
            "máy hâm sữa siêu tốc",
            "xe đẩy em bé gấp gọn đi du lịch",
            "ghế ăn dặm cho bé điều chỉnh độ cao",
            "nồi nấu cháo chậm bear cho bé",
            "khăn ướt không mùi dịu nhẹ cho bé",
            "sữa tắm gội thảo dược cho bé",
            "đồ chơi xúc xắc gặm nướu silicon",
            "bộ xếp hình lego chính hãng",
            "nhiệt kế hồng ngoại đo trán",
            "yếm ăn dặm silicon có máng"
        ]
    },
    {
        "id": "home_living",
        "name": "Nhà Cửa & Đời Sống",
        "icon": "🪑",
        "keywords": [
            "bình giữ nhiệt lock&lock chính hãng",
            "ly giữ nhiệt inox 304 có ống hút",
            "bộ nồi chảo chống dính tefal",
            "chảo chống dính sâu lòng phủ đá hoa cương",
            "bộ dao nhà bếp thép không gỉ",
            "kệ để bát đĩa đa năng thông minh",
            "kệ để giày dép 5 tầng khung thép",
            "hộp đựng thực phẩm thủy tinh chia ngăn",
            "bộ ga gối cotton tencel mềm mát",
            "gối cao su non nâng đỡ cổ vai gáy",
            "nệm topper làm mềm đệm xuất nhật",
            "đèn bàn học chống cận thị led",
            "đèn ngủ cảm ứng đổi màu",
            "tinh dầu xông phòng thơm phòng thiên nhiên",
            "máy khuếch tán tinh dầu siêu âm",
            "cây lau nhà thông minh tự vắt xoay 360",
            "thùng rác thông minh cảm ứng tự mở",
            "hộp đựng cơm cắm điện giữ nhiệt",
            "két sắt mini thông minh vân tay",
            "khăn tắm lông cừu xuất hàn siêu thấm"
        ]
    },
    {
        "id": "tools_hardware",
        "name": "Dụng Cụ Cầm Tay & Sửa Chữa",
        "icon": "🧰",
        "keywords": [
            "máy khoan pin không chổi than 21v",
            "máy siết bulong pin lực lớn",
            "máy mài góc cầm tay dùng pin",
            "máy rửa xe mini áp lực cao gia đình",
            "bộ cờ lê mỏ lết đa năng 46 chi tiết",
            "bộ tua vít sửa chữa điện thoại máy tính",
            "thước đo khoảng cách laser 40m",
            "kìm bấm chết đa năng thép cr-v",
            "bút thử điện thông minh cảm ứng không tiếp xúc",
            "máy hàn que mini gia đình inverter",
            "máy cưa xích pin cầm tay cắt tỉa cành",
            "thang nhôm rút chữ a thông minh",
            "máy xịt rửa điều hòa máy lạnh",
            "bơm lốp xe đạp xe máy có đồng hồ",
            "súng bắn keo nến nhiệt nhanh",
            "đèn pin siêu sáng chiếu xa 1000m",
            "mỏ hàn chì điện tử chỉnh nhiệt độ",
            "hộp đựng đồ nghề sửa chữa chuyên dụng",
            "kính lúp có đèn led để bàn",
            "bộ vam cảo tháo vòng bi đa năng"
        ]
    },
    {
        "id": "auto_motorcycle",
        "name": "Phụ Kiện Ô Tô & Xe Máy",
        "icon": "🚗",
        "keywords": [
            "camera hành trình 70mai 4k chính hãng",
            "máy bơm lốp ô tô xiaomi 70mai tự ngắt",
            "tẩu sạc nhanh ô tô 65w 2 cổng",
            "cảm biến áp suất lốp gắn trong năng lượng mặt trời",
            "máy hút bụi ô tô mini không dây lực hút khỏe",
            "bạt phủ xe ô tô tráng nhôm cách nhiệt",
            "giá đỡ điện thoại ô tô kiêm sạc không dây",
            "nước hoa ô tô kẹp cửa gió cao cấp",
            "gối tựa đầu tựa lưng cao su non ô tô",
            "thảm lót sàn ô tô 5d 6d theo xe",
            "mũ bảo hiểm 3/4 royal chính hãng",
            "mũ bảo hiểm fullface 2 kính",
            "dầu nhớt motul xe ga 10w40 chính hãng",
            "dầu nhớt repsol xe số tổng hợp",
            "giá đỡ điện thoại gắn chân gương xe máy kim loại",
            "gương chiếu hậu xe máy gù tay lái",
            "bọc yên xe máy chống nóng 3d",
            "khóa đĩa xe máy báo động chống trộm",
            "áo mưa cánh dơi 2 đầu chống thấm vải dù",
            "đèn led trợ sáng xe máy gom sáng"
        ]
    },
    {
        "id": "watches_jewelry",
        "name": "Đồng Hồ & Mắt Kính",
        "icon": "⌚",
        "keywords": [
            "đồng hồ thông minh theo dõi nhịp tim spo2",
            "smartwatch vòng đeo tay miband chính hãng",
            "đồng hồ nam dây kim loại máy nhật chống nước",
            "đồng hồ nam lộ cơ máy automatic",
            "đồng hồ nam thể thao 6 kim chronograph",
            "đồng hồ nữ đính đá sang trọng dây da",
            "đồng hồ nữ mặt vuông phong cách vintage",
            "kính râm phân cực chống tia uv400 nam",
            "kính mát nữ gọng kim loại mắt mèo thời trang",
            "gọng kính cận titan siêu nhẹ nam nữ",
            "vòng tay phong thủy đá tự nhiên",
            "lắc tay bạc nữ cỏ 4 lá may mắn",
            "dây chuyền bạc ý 925 mặt tròn nữ",
            "nhẫn bạc nam phong cách titan cá tính",
            "khuyên tai bạc nữ tròn đính đá nụ",
            "hộp đựng đồng hồ trang sức 6 ngăn bọc da",
            "dây da đồng hồ bò sáp handmade khóa bấm",
            "dây đồng hồ kim loại thép không gỉ mắt lưới",
            "dụng cụ cắt mắt dây đồng hồ tại nhà",
            "khăn lau kính mắt chống mờ sương"
        ]
    },
    {
        "id": "groceries",
        "name": "Bách Hóa Online & Tiêu Dùng",
        "icon": "🛒",
        "keywords": [
            "cà phê hòa tan g7 trung nguyên 3 in 1",
            "cà phê đen hòa tan sấy lạnh nescafe",
            "trà sữa phúc long đóng lon hòa tan",
            "trà ô long túi lọc cao cấp",
            "hạt điều rang muối bình phước nguyên hạt",
            "hạt macca sấy nứt vỏ úc kèm dụng cụ tách",
            "hạt dẻ cười mỹ sấy nguyên vị không tẩy",
            "bánh quy bơ danisa hoàng gia đan mạch",
            "thanh ngũ cốc granola ăn kiêng giảm cân",
            "nước giặt xả omo matic cửa trước",
            "nước giặt ariel đậm đặc túi tiết kiệm",
            "nước xả vải comfort hương nước hoa ban mai",
            "nước rửa chén sunlight thiên nhiên chanh quế",
            "viên giặt xả 3 in 1 công nghệ nhật bản",
            "giấy vệ sinh cuộn cao cấp 4 lớp không lõi",
            "khăn giấy rút lụa đa năng ăn dặm",
            "màng bọc thực phẩm pe có lưỡi dao cắt",
            "túi rác tự hủy sinh học dạng cuộn dai",
            "viên tẩy bồn cầu khử mùi diệt khuẩn",
            "nước lau sàn đuổi côn trùng hương sả quế"
        ]
    }
]

def init_radar_categories_table():
    """Đảm bảo bảng lazada_radar_categories đã được nạp dữ liệu ban đầu."""
    try:
        count_row = db.q("SELECT COUNT(*) as c FROM lazada_radar_categories", one=True)
        if not count_row or count_row["c"] == 0:
            reset_radar_categories_to_default()
    except Exception as e:
        print("[lazada_general_scanner] init_radar_categories_table notice:", e)

def get_radar_categories(active_only: bool = False) -> List[Dict[str, Any]]:
    """Lấy danh sách các ngành hàng và từ khóa Radar từ database."""
    try:
        init_radar_categories_table()
        sql = "SELECT * FROM lazada_radar_categories"
        if active_only:
            sql += " WHERE is_active=1"
        sql += " ORDER BY sort_order ASC, name ASC"
        rows = db.q(sql)
        cats = []
        for r in rows:
            try:
                kws = json.loads(r.get("keywords_json") or "[]")
            except Exception:
                kws = []
            cats.append({
                "id": r["id"],
                "name": r["name"],
                "icon": r.get("icon") or "🏷️",
                "keywords": kws,
                "keywords_count": len(kws),
                "is_active": bool(r.get("is_active", 1)),
                "sort_order": r.get("sort_order", 0)
            })
        return cats
    except Exception as e:
        print("[lazada_general_scanner] get_radar_categories error, falling back to default:", e)
        return DEFAULT_GENERAL_CATEGORIES

def save_radar_category(cat_id: str, name: str, icon: str, keywords: List[str], is_active: bool = True, sort_order: int = 0) -> Dict[str, Any]:
    """Thêm hoặc cập nhật một ngành hàng và danh sách từ khóa trong radar."""
    now = time.time()
    kw_clean = [k.strip() for k in keywords if k and k.strip()]
    db.x("""
        INSERT INTO lazada_radar_categories(id, name, icon, keywords_json, is_active, sort_order, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            icon=excluded.icon,
            keywords_json=excluded.keywords_json,
            is_active=excluded.is_active,
            sort_order=excluded.sort_order,
            updated_at=excluded.updated_at
    """, (cat_id, name, icon, json.dumps(kw_clean, ensure_ascii=False), 1 if is_active else 0, sort_order, now, now))
    return {
        "id": cat_id,
        "name": name,
        "icon": icon,
        "keywords": kw_clean,
        "keywords_count": len(kw_clean),
        "is_active": is_active,
        "sort_order": sort_order
    }

def delete_radar_category(cat_id: str) -> bool:
    """Xóa một ngành hàng khỏi radar."""
    db.x("DELETE FROM lazada_radar_categories WHERE id=?", (cat_id,))
    return True

def reset_radar_categories_to_default() -> List[Dict[str, Any]]:
    """Xóa và nạp lại kho từ khóa chuẩn 13 ngành / 260 từ khóa."""
    now = time.time()
    db.x("DELETE FROM lazada_radar_categories")
    for idx, cat in enumerate(DEFAULT_GENERAL_CATEGORIES):
        db.x("""
            INSERT INTO lazada_radar_categories(id, name, icon, keywords_json, is_active, sort_order, created_at, updated_at)
            VALUES(?, ?, ?, ?, 1, ?, ?, ?)
        """, (cat["id"], cat["name"], cat.get("icon", "🏷️"), json.dumps(cat["keywords"], ensure_ascii=False), idx, now, now))
    return get_radar_categories()

def sync_lazada_official_categories() -> Dict[str, Any]:
    """Cào trực tiếp cây danh mục & gợi ý tìm kiếm từ Lazada Việt Nam để cập nhật vào Kho từ khóa Radar."""
    import requests, urllib.parse
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    init_radar_categories_table()
    current_cats = {c["id"]: c for c in get_radar_categories()}
    added_count = 0
    updated_count = 0

    try:
        r = requests.get('https://www.lazada.vn/', headers=headers, timeout=12)
        html = r.text
        matches = re.findall(r'params=([^&"\'\s]+)', html)
        seen = set()
        
        for m in matches:
            try:
                decoded = urllib.parse.unquote(m)
                j = json.loads(decoded)
                if 'categoryName' in j and 'categoryId' in j:
                    raw_name = urllib.parse.unquote(j['categoryName']).replace('+', ' ').strip()
                    cid = str(j['categoryId'])
                    if not raw_name or raw_name in seen:
                        continue
                    seen.add(raw_name)

                    # Tìm xem ngành này đã khớp với ID nào chưa
                    matched_id = None
                    for existing_id, c_data in current_cats.items():
                        if c_data["name"].lower() in raw_name.lower() or raw_name.lower() in c_data["name"].lower():
                            matched_id = existing_id
                            break

                    if matched_id:
                        # Bổ sung từ khóa gợi ý nếu chưa có
                        curr_kws = current_cats[matched_id]["keywords"]
                        candidate_kw = raw_name.lower()
                        if candidate_kw not in [k.lower() for k in curr_kws]:
                            curr_kws.append(candidate_kw)
                            save_radar_category(
                                matched_id,
                                current_cats[matched_id]["name"],
                                current_cats[matched_id]["icon"],
                                curr_kws,
                                current_cats[matched_id]["is_active"],
                                current_cats[matched_id]["sort_order"]
                            )
                            updated_count += 1
                    else:
                        # Thêm ngành hàng mới phát hiện
                        new_cat_id = f"laz_cat_{cid}"
                        suggested_kws = [
                            raw_name.lower(),
                            f"{raw_name.lower()} chính hãng",
                            f"{raw_name.lower()} giảm sốc"
                        ]
                        save_radar_category(
                            new_cat_id,
                            raw_name,
                            "🏷️",
                            suggested_kws,
                            True,
                            len(current_cats) + 1
                        )
                        added_count += 1
            except Exception:
                pass
    except Exception as e:
        print("[lazada_general_scanner] Lỗi cào danh mục trực tiếp:", e)

    all_cats = get_radar_categories()
    total_kws = sum(c["keywords_count"] for c in all_cats)
    return {
        "success": True,
        "message": f"Đã quét và đồng bộ thành công danh mục Lazada ({len(all_cats)} ngành hàng, {total_kws} từ khóa radar)!",
        "total_categories": len(all_cats),
        "total_keywords": total_kws,
        "added_categories": added_count,
        "updated_categories": updated_count,
        "categories": all_cats
    }

# Danh sách từ khóa phụ kiện / linh kiện đa ngành để loại trừ bẫy giá rẻ của shop
ACCESSORY_KEYWORDS = [
    # Phụ kiện phím chuột máy tính
    "che bui", "dust cover", "dustcover", "nap day", "tam day",
    "day cap", "cap type c", "type c", "day lo xo", "coiled cable", "cap sac",
    "switch le", "combo switch", "pack switch", "set switch", "1 switch", "10 switch", "30 switch", "45 switch",
    "keycap", "key cap", "nut ban phim", "bo keycap",
    "num xoay", "knob", "num kim loai",
    "tui dung", "bao da", "tui chong soc",
    "foam", "pad chuot", "lot chuot", "mousepad", "feet chuot", "grip tape",
    "plate", "mach pcb", "stab", "lubing", "dung cu", "keypuller", "switch puller",
    # Phụ kiện điện tử / di động
    "mieng dan", "op lung", "kinh cuong luc", "day deo", "dau chuyen", "dau otg", "nut chong dut", "day quan",
    "hop dung tai nghe", "tips tai nghe", "dem tai thay the",
    # Phụ kiện gia dụng / chăm sóc cá nhân
    "dau thay the", "luoi dao thay the", "dau tam nuoc", "dau ban chai thay the", "mang loc thay the",
    "voi xit", "ong hut le", "gioang cao su", "nap binh le", "choi ve sinh",
    # Phụ kiện thời trang
    "day giay", "lot giay", "tat le", "vo le", "hop giay rong", "moc treo"
]

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def normalize_text(text: str) -> str:
    text = remove_accents(text).lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def get_general_scanner_config() -> Dict[str, Any]:
    """Đọc cấu hình lazada_general_scanner từ config.yaml."""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    try:
        import yaml
        data = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
        return data.get("lazada_general_scanner", {
            "enabled": True,
            "interval_minutes": 5,
            "min_drop_pct": 80.0,
            "tmall_min_drop_pct": 80.0,
            "tmall_max_drop_pct": 95.0,
            "min_price_floor": 35000.0,
            "batch_keywords_per_cycle": 6
        })
    except Exception:
        return {
            "enabled": True,
            "interval_minutes": 5,
            "min_drop_pct": 80.0,
            "tmall_min_drop_pct": 80.0,
            "tmall_max_drop_pct": 95.0,
            "min_price_floor": 35000.0,
            "batch_keywords_per_cycle": 6
        }

def save_general_scanner_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """Lưu cấu hình lazada_general_scanner vào config.yaml."""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    data = {}
    try:
        import yaml
        data = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
    except Exception:
        pass
    curr = data.get("lazada_general_scanner", {})
    curr.update(new_config)
    data["lazada_general_scanner"] = curr
    import yaml
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return curr

_general_scanner_status: Dict[str, Any] = {
    "is_running": False,
    "trigger_type": "none",
    "started_at": 0,
    "current_category": "",
    "current_keyword": "",
    "total_keywords": 0,
    "current_index": 0,
    "items_scanned": 0,
    "deals_found": 0,
    "message": "Sẵn sàng",
    "last_finished_at": 0,
    "last_result": None
}

_keyword_rotation_pointer: int = 0

def get_general_scanner_status() -> Dict[str, Any]:
    global _general_scanner_status
    st = dict(_general_scanner_status)
    if st["is_running"] and st["started_at"] > 0:
        st["elapsed_seconds"] = int(time.time() - st["started_at"])
    else:
        st["elapsed_seconds"] = 0
    return st

def is_accessory_trap(title: str, variation_name: str = "") -> Tuple[bool, str]:
    """Kiểm tra sản phẩm hoặc phân loại có phải là bẫy phụ kiện giá rẻ không."""
    norm_title = normalize_text(title)
    norm_var = normalize_text(variation_name)

    for acc in ACCESSORY_KEYWORDS:
        if acc in norm_var:
            return True, f"Phân loại chứa phụ kiện: '{acc}'"
        if acc in norm_title and not any(k in norm_title for k in ["ban phim", "tai nghe", "chuot", "giay", "ao", "may", "noi"]):
            return True, f"Tiêu đề là phụ kiện: '{acc}'"
    return False, "Hợp lệ"

def format_deep_drop_telegram(deal: Dict[str, Any]) -> str:
    """Tạo tin nhắn Telegram chuyên biệt cho deal sập sàn phân loại / Tmall deep drop."""
    title = deal.get("product_title", "")
    var_name = deal.get("variation_name") or "Toàn bộ / Mặc định"
    seller = deal.get("seller_name", "Gian hàng chính hãng")
    category = deal.get("category", "Tổng Hợp")
    drop_price = deal.get("drop_price", 0)
    sibling_price = deal.get("sibling_avg_price", 0)
    drop_pct = deal.get("drop_pct", 0)
    save_amount = sibling_price - drop_price if sibling_price > drop_price else 0
    stock = deal.get("stock", 1)
    url = deal.get("product_url", "https://www.lazada.vn/")
    time_str = time.strftime("%H:%M:%S - %d/%m/%Y")

    stock_text = f"📦 <b>Tồn kho còn:</b> <code>{stock} chiếc</code> (Bấm mua ngay kẻo hết!)\n" if stock > 0 else ""

    msg = (
        f"🚨 <b>[KÈO SẬP SÀN TMALL / LAZMALL - GIẢM THẲNG {drop_pct:.0f}%]</b> 🚨\n\n"
        f"📦 <b>Sản phẩm:</b> {title}\n"
        f"🏷️ <b>Ngành hàng:</b> {category}\n"
        f"🏪 <b>Gian hàng:</b> {seller} (🎖️ <b>LazMall / Tmall</b>)\n\n"
        f"👉 <b>Phân loại giảm sâu:</b> <code>{var_name}</code>\n"
        f"💰 <b>Giá sập sàn:</b> <code>{drop_price:,.0f} đ</code> <i>(Giảm trực tiếp, không cần mã!)</i>\n"
        f"📊 <b>Giá gốc / phân loại khác:</b> <code>{sibling_price:,.0f} đ</code>\n"
        f"📉 <b>Mức giảm:</b> <b>-{drop_pct:.1f}%</b> (Tiết kiệm <b>{save_amount:,.0f} đ</b>)\n"
        f"{stock_text}\n"
        f"🛒 <b>Link săn ngay:</b> <a href=\"{url}\">Bấm vào đây để mua sản phẩm</a>\n"
        f"⏰ <i>Radar quét lúc: {time_str}</i>"
    )
    return msg

def run_general_scanner_cycle(
    selected_categories: Optional[List[str]] = None,
    min_drop_pct: Optional[float] = None,
    min_price_floor: Optional[float] = None,
    limit_per_kw: int = 30,
    trigger_type: str = "manual"
) -> Dict[str, Any]:
    """Chạy một chu kỳ quét tổng quát toàn sàn Lazada LazMall:
    - Quét qua danh sách các từ khóa đa ngành hàng
    - Lọc sản phẩm LazMall có mức giảm sâu >= min_drop_pct
    - Loại trừ các bẫy phụ kiện
    - Gửi cảnh báo Telegram & lưu DB
    """
    global _general_scanner_status, _keyword_rotation_pointer
    if _general_scanner_status.get("is_running"):
        return {
            "status": "already_running",
            "message": "Luồng quét tổng quát đang chạy, vui lòng đợi hoàn tất."
        }

    cfg = get_general_scanner_config()
    eff_min_drop = min_drop_pct if min_drop_pct is not None else float(cfg.get("min_drop_pct", 50.0))
    eff_min_floor = min_price_floor if min_price_floor is not None else float(cfg.get("min_price_floor", 35000.0))
    filter_mall = bool(cfg.get("filter_mall_only", True))

    start_time = time.time()
    _general_scanner_status.update({
        "is_running": True,
        "trigger_type": trigger_type,
        "started_at": start_time,
        "current_category": "",
        "current_keyword": "",
        "total_keywords": 0,
        "current_index": 0,
        "items_scanned": 0,
        "deals_found": 0,
        "message": "Đang khởi động radar quét tổng quát LazMall / Tmall..."
    })

    # Thu thập danh sách từ khóa cần quét từ DB (hoặc mặc định mở rộng)
    all_radar_cats = get_radar_categories(active_only=True)
    active_categories = []
    for cat in all_radar_cats:
        if not selected_categories or cat["id"] in selected_categories or cat["name"] in selected_categories:
            active_categories.append(cat)

    all_tasks = []
    for cat in active_categories:
        for kw in cat["keywords"]:
            all_tasks.append({
                "category_id": cat["id"],
                "category_name": cat["name"],
                "keyword": kw
            })

    if not all_tasks:
        _general_scanner_status["is_running"] = False
        return {"status": "error", "message": "Không có từ khóa nào để quét."}

    # Nếu chạy định kỳ 5 phút (auto_5m), thực hiện xoay vòng batch_keywords để tối ưu tốc độ (~30s/chu kỳ)
    if trigger_type == "auto_5m":
        batch_size = int(cfg.get("batch_keywords_per_cycle", 6))
        start_idx = _keyword_rotation_pointer % len(all_tasks)
        tasks_to_run = []
        for i in range(min(batch_size, len(all_tasks))):
            tasks_to_run.append(all_tasks[(start_idx + i) % len(all_tasks)])
        _keyword_rotation_pointer = (start_idx + len(tasks_to_run)) % len(all_tasks)
    else:
        tasks_to_run = all_tasks

    _general_scanner_status["total_keywords"] = len(tasks_to_run)
    deals_found_count = 0
    items_scanned_count = 0
    now = time.time()
    day_ago = now - 86400  # 24 giờ qua

    # Tạo bản ghi log ban đầu
    log_id = db.x("""
        INSERT INTO lazada_deep_drops_logs(
            started_at, finished_at, status, categories_scanned,
            items_scanned, deals_found, telegram_sent, message, created_at
        ) VALUES (?, 0, 'running', ?, 0, 0, 0, 'Đang quét toàn sàn...', ?)
    """, (start_time, json.dumps([c["id"] for c in active_categories]), start_time))

    try:
        for idx, task in enumerate(tasks_to_run, 1):
            cat_name = task["category_name"]
            kw = task["keyword"]

            _general_scanner_status["current_index"] = idx
            _general_scanner_status["current_category"] = cat_name
            _general_scanner_status["current_keyword"] = kw
            _general_scanner_status["message"] = f"Đang quét [{idx}/{len(tasks_to_run)}]: {cat_name} - '{kw}'"

            try:
                # Tìm kiếm sản phẩm LazMall
                items = lazada.search_lazada_products(kw, filter_mall_only=filter_mall, limit=limit_per_kw)
                items = items or []
                items_scanned_count += len(items)
                _general_scanner_status["items_scanned"] = items_scanned_count

                for it in items:
                    # Chỉ lấy LazMall / Tmall
                    if not it.get("is_mall", False):
                        continue

                    item_id = str(it.get("item_id", ""))
                    title = it.get("title", "")
                    seller_name = it.get("seller_name", "LazMall")
                    product_url = it.get("product_url", "")
                    image_url = it.get("image_url", "")
                    price_val = float(it.get("price", 0))
                    orig_val = float(it.get("orig_price", 0))
                    variations = it.get("variations") or []

                    # 1. Kiểm tra giá sàn tối thiểu (loại trừ các món quà tặng lặt vặt < 35k)
                    if price_val < eff_min_floor:
                        continue

                    # 2. Phát hiện mức giảm giá:
                    # Trường hợp A: Có giá gốc niêm yết (orig_price)
                    # Trường hợp B: Sản phẩm có nhiều biến thể với giá chênh lệch
                    calc_drop_pct = 0.0
                    ref_price = orig_val

                    if orig_val > price_val and orig_val > 0:
                        calc_drop_pct = round(((orig_val - price_val) / orig_val) * 100.0, 1)

                    # Duyệt qua các phân loại nếu có
                    var_prices = [float(v.get("price") or price_val) for v in variations if float(v.get("price") or price_val) > 0]
                    if not var_prices:
                        var_prices = [price_val] if price_val > 0 else []

                    for var in variations:
                        var_name = var.get("name") or "Mặc định"
                        sku_id = str(var.get("sku_id") or item_id)
                        var_price = float(var.get("price") or price_val)

                        # Bỏ qua nếu giá quá thấp (bẫy rác)
                        if var_price < eff_min_floor:
                            continue

                        # 3. Lọc bẫy phụ kiện
                        is_trap, trap_reason = is_accessory_trap(title, var_name)
                        if is_trap:
                            continue

                        # Tính drop_pct cho biến thể này:
                        # Cách A: Dựa trên giá niêm yết (orig_val)
                        eff_drop = calc_drop_pct
                        eff_ref = ref_price

                        # Cách B: Dựa trên chênh lệch với các phân loại anh em (Sibling Gap)
                        other_sibling_prices = [p for p in var_prices if p != var_price]
                        if other_sibling_prices:
                            sibling_avg = sum(other_sibling_prices) / len(other_sibling_prices)
                            if sibling_avg > var_price and sibling_avg > 0:
                                sibling_drop_pct = round(((sibling_avg - var_price) / sibling_avg) * 100.0, 1)
                                if sibling_drop_pct > eff_drop:
                                    eff_drop = sibling_drop_pct
                                    eff_ref = sibling_avg

                        # Kiểm tra ngưỡng chiết khấu tối thiểu và trần tối đa (tránh bug giá ảo 99%)
                        if eff_drop < eff_min_drop or eff_drop > 92.0:
                            continue

                        # 4. Kiểm tra chống trùng lặp trong 24h
                        recent = db.q("""
                            SELECT id FROM lazada_deep_drops
                            WHERE item_id = ? AND sku_id = ? AND created_at > ?
                        """, (item_id, sku_id, day_ago), one=True)

                        if not recent:
                            deal_data = {
                                "item_id": item_id,
                                "sku_id": sku_id,
                                "product_title": title,
                                "category": cat_name,
                                "variation_name": var_name,
                                "sibling_count": len(variations),
                                "sibling_avg_price": eff_ref,
                                "drop_price": var_price,
                                "drop_pct": eff_drop,
                                "stock": 10,
                                "seller_name": seller_name,
                                "is_mall": 1,
                                "product_url": product_url,
                                "image_url": image_url
                            }

                            # Gửi thông báo Telegram
                            try:
                                tg_msg = format_deep_drop_telegram(deal_data)
                                tg(tg_msg, parse_mode="HTML")
                            except Exception as tg_err:
                                print(f"[general_scanner] Lỗi gửi Telegram: {tg_err}")

                            # Lưu vào database
                            db.x("""
                                INSERT INTO lazada_deep_drops(
                                    item_id, sku_id, product_title, category, variation_name,
                                    sibling_count, sibling_avg_price, drop_price, drop_pct,
                                    stock, seller_name, is_mall, product_url, image_url,
                                    sent_to_tg, sent_to_tg_at, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """, (
                                item_id, sku_id, title, cat_name, var_name,
                                len(variations), eff_ref, var_price, eff_drop,
                                10, seller_name, 1, product_url, image_url,
                                now, now
                            ))

                            deals_found_count += 1
                            _general_scanner_status["deals_found"] = deals_found_count

            except Exception as kw_err:
                print(f"[general_scanner] Lỗi quét '{kw}': {kw_err}")

        finish_time = time.time()
        final_msg = f"Đã quét xong {items_scanned_count} sản phẩm LazMall, phát hiện {deals_found_count} kèo sập sàn sâu."
        _general_scanner_status.update({
            "is_running": False,
            "last_finished_at": finish_time,
            "last_result": final_msg,
            "message": final_msg
        })

        db.x("""
            UPDATE lazada_deep_drops_logs
            SET finished_at = ?, status = 'success', items_scanned = ?, deals_found = ?,
                telegram_sent = ?, message = ?
            WHERE id = ?
        """, (finish_time, items_scanned_count, deals_found_count, deals_found_count, final_msg, log_id))

        return {
            "status": "success",
            "message": final_msg,
            "items_scanned": items_scanned_count,
            "deals_found": deals_found_count
        }

    except Exception as e:
        finish_time = time.time()
        err_msg = f"Lỗi chu kỳ quét: {e}"
        _general_scanner_status.update({
            "is_running": False,
            "last_finished_at": finish_time,
            "last_result": err_msg,
            "message": err_msg
        })
        db.x("""
            UPDATE lazada_deep_drops_logs
            SET finished_at = ?, status = 'error', message = ?
            WHERE id = ?
        """, (finish_time, err_msg, log_id))
        return {
            "status": "error",
            "message": err_msg,
            "deals_found": deals_found_count
        }
    finally:
        _general_scanner_status["is_running"] = False

# ==============================================================================
# PHẦN QUÉT DEAL TMALL BRAND (THEO NHÓM NGÀNH & DANH SÁCH SHOP TRÊN TMALL LAZADA)
# ==============================================================================

TARGET_TMALL_CATEGORY_NAMES = [
    "Điện Gia Dụng",
    "Điện Tử & Phụ Kiện",
    "Bách Hóa",
    "Đời Sống",
    "Thời Trang Thể Thao",
    "Thời Trang Nam"
]

TMALL_CATEGORY_ICONS = {
    "0": "✨",  # Mới lên Kệ
    "1": "💄",  # Làm Đẹp
    "2": "🍳",  # Điện Gia Dụng
    "3": "💻",  # Điện Tử & Phụ Kiện
    "4": "🧦",  # Đồ Lót & Phụ Kiện
    "5": "👠",  # Giày Dép
    "6": "👔",  # Thời Trang Nam
    "7": "👗",  # Thời Trang Nữ
    "8": "👟",  # Thời Trang Thể Thao
    "9": "🛒",  # Bách Hóa
    "10": "👶", # Mẹ & Bé
    "11": "🐱", # Thú Cưng
    "12": "🪑", # Đời Sống
    "13": "⛺", # Ngoài Trời
    "14": "🚗"  # Xe Máy & Ô tô
}

_tmall_continuous_running: bool = False
_tmall_continuous_stop_requested: bool = False
_tmall_continuous_thread: Optional[threading.Thread] = None
_tmall_continuous_loop_count: int = 0

_tmall_brand_scanner_status: Dict[str, Any] = {
    "is_running": False,
    "continuous_mode": False,
    "current_loop": 0,
    "trigger_type": "none",
    "started_at": 0,
    "elapsed_seconds": 0,
    "current_category_name": "",
    "current_shop_name": "",
    "current_shop_index": 0,
    "total_shops": 0,
    "items_scanned": 0,
    "deals_found": 0,
    "message": "",
    "last_finished_at": 0,
    "last_result": None
}

_tmall_shop_rotation_pointer: int = 0

def init_tmall_brands_tables():
    """Khởi tạo và nạp dữ liệu ban đầu cho các bảng Tmall Brand Categories & Shops."""
    try:
        count_row = db.q("SELECT COUNT(*) as c FROM lazada_tmall_categories", one=True)
        if count_row and count_row["c"] > 0:
            return

        seed_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tmall_brands_seed.json")
        if not os.path.exists(seed_file):
            return

        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        full_data = data.get("full_data", {})
        now = time.time()

        for idx, (cid, c_info) in enumerate(full_data.items()):
            cname = c_info.get("name")
            icon = TMALL_CATEGORY_ICONS.get(str(cid), "🏪")
            is_target = any(t.lower() == cname.lower() for t in TARGET_TMALL_CATEGORY_NAMES)
            is_active = 1 if is_target else 0
            shops = c_info.get("shops", [])

            db.x("""
                INSERT INTO lazada_tmall_categories(id, name, icon, is_active, sort_order, shops_count, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    icon=excluded.icon,
                    sort_order=excluded.sort_order,
                    shops_count=excluded.shops_count,
                    updated_at=excluded.updated_at
            """, (str(cid), cname, icon, is_active, idx, len(shops), now, now))

            for s in shops:
                s_name = s.get("name", "")
                s_url = s.get("url", "")
                s_img = s.get("img", "")
                slug = s_url.split("?")[0].rstrip("/").split("/")[-1] if "/" in s_url else s_name.lower().replace(" ", "-")

                db.x("""
                    INSERT INTO lazada_tmall_shops(
                        category_id, category_name, shop_name, shop_slug, shop_url, logo_url, is_active, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(category_id, shop_slug) DO UPDATE SET
                        shop_name=excluded.shop_name,
                        shop_url=excluded.shop_url,
                        logo_url=excluded.logo_url,
                        updated_at=excluded.updated_at
                """, (str(cid), cname, s_name, slug, s_url, s_img, now, now))

    except Exception as e:
        print("[lazada_general_scanner] init_tmall_brands_tables notice:", e)

def get_tmall_categories(active_only: bool = False) -> List[Dict[str, Any]]:
    """Lấy danh sách các nhóm ngành Tmall Brand kèm số lượng shop và deal đã săn."""
    init_tmall_brands_tables()
    sql = "SELECT * FROM lazada_tmall_categories"
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY sort_order ASC, name ASC"
    rows = db.q(sql)

    # Đếm số lượng deal đã phát hiện theo từng nhóm ngành
    deal_counts = {}
    try:
        cnt_rows = db.q("SELECT category, COUNT(*) as c FROM lazada_deep_drops GROUP BY category")
        for cr in cnt_rows:
            if cr.get("category"):
                deal_counts[cr["category"].lower().strip()] = cr["c"]
    except Exception:
        pass

    cats = []
    for r in rows:
        c_name = r["name"]
        d_cnt = deal_counts.get(c_name.lower().strip(), 0)
        cats.append({
            "id": r["id"],
            "name": c_name,
            "icon": r.get("icon") or "🏪",
            "is_active": bool(r.get("is_active", 1)),
            "sort_order": r.get("sort_order", 0),
            "shops_count": r.get("shops_count", 0),
            "deals_count": d_cnt
        })
    return cats

def toggle_tmall_category(cat_id: str, is_active: bool) -> Dict[str, Any]:
    """Bật/tắt kích hoạt một nhóm ngành Tmall để radar tập trung quét."""
    now = time.time()
    db.x("UPDATE lazada_tmall_categories SET is_active=?, updated_at=? WHERE id=?", (1 if is_active else 0, now, cat_id))
    db.x("UPDATE lazada_tmall_shops SET is_active=?, updated_at=? WHERE category_id=?", (1 if is_active else 0, now, cat_id))
    return {"success": True, "category_id": cat_id, "is_active": is_active}

def get_tmall_shops(category_id: Optional[str] = None, active_only: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
    """Lấy danh sách các shop trong nhóm ngành Tmall."""
    init_tmall_brands_tables()
    sql = "SELECT * FROM lazada_tmall_shops WHERE 1=1"
    args = []
    if category_id:
        sql += " AND category_id = ?"
        args.append(category_id)
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY deals_found_count DESC, shop_name ASC LIMIT ?"
    args.append(limit)
    rows = db.q(sql, tuple(args))
    return [dict(r) for r in rows]

def sync_tmall_brands_directory() -> Dict[str, Any]:
    """Cào trực tiếp danh mục Brand Tmall và các shop mới nhất từ Lazada."""
    raw = lazada.sync_tmall_brand_directory_live()
    full_data = raw.get("full_data", {})
    if not full_data:
        return {"success": False, "message": "Không lấy được dữ liệu từ Lazada Tmall."}

    now = time.time()
    for idx, (cid, c_info) in enumerate(full_data.items()):
        cname = c_info.get("name")
        icon = TMALL_CATEGORY_ICONS.get(str(cid), "🏪")
        is_target = any(t.lower() == cname.lower() for t in TARGET_TMALL_CATEGORY_NAMES)
        shops = c_info.get("shops", [])

        db.x("""
            INSERT INTO lazada_tmall_categories(id, name, icon, is_active, sort_order, shops_count, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                icon=excluded.icon,
                shops_count=excluded.shops_count,
                updated_at=excluded.updated_at
        """, (str(cid), cname, icon, 1 if is_target else 0, idx, len(shops), now, now))

        for s in shops:
            s_name = s.get("name", "")
            s_url = s.get("url", "")
            s_img = s.get("img", "")
            slug = s_url.split("?")[0].rstrip("/").split("/")[-1] if "/" in s_url else s_name.lower().replace(" ", "-")

            db.x("""
                INSERT INTO lazada_tmall_shops(
                    category_id, category_name, shop_name, shop_slug, shop_url, logo_url, is_active, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(category_id, shop_slug) DO UPDATE SET
                    shop_name=excluded.shop_name,
                    shop_url=excluded.shop_url,
                    logo_url=excluded.logo_url,
                    updated_at=excluded.updated_at
            """, (str(cid), cname, s_name, slug, s_url, s_img, now, now))

    cats = get_tmall_categories()
    total_shops = sum(c["shops_count"] for c in cats)
    return {
        "success": True,
        "message": f"Đã đồng bộ thành công {len(cats)} nhóm ngành và {total_shops} shop Tmall Brand!",
        "categories": cats,
        "total_categories": len(cats),
        "total_shops": total_shops
    }

def get_tmall_brand_scanner_status() -> Dict[str, Any]:
    """Lấy trạng thái thực thi hiện tại của Radar quét Tmall Brand."""
    st = dict(_tmall_brand_scanner_status)
    st["continuous_mode"] = _tmall_continuous_running
    st["current_loop"] = _tmall_continuous_loop_count
    if st.get("is_running") and st.get("started_at"):
        st["elapsed_seconds"] = int(time.time() - st["started_at"])
    return st

def format_tmall_brand_telegram(deal: Dict[str, Any]) -> str:
    """Tạo tin nhắn Telegram chuyên biệt cho deal sập sàn từ shop Brand Tmall chính hãng."""
    title = deal.get("product_title", "")
    seller = deal.get("seller_name", "Gian hàng chính hãng")
    category = deal.get("category", "Tmall Brand")
    drop_price = deal.get("drop_price", 0)
    sibling_price = deal.get("sibling_avg_price", 0)
    drop_pct = deal.get("drop_pct", 0)
    save_amount = sibling_price - drop_price if sibling_price > drop_price else 0
    url = deal.get("product_url", "https://www.lazada.vn/")
    time_str = time.strftime("%H:%M:%S - %d/%m/%Y")

    msg = (
        f"🚨 <b>[KÈO SẬP SÀN BRAND TMALL - GIẢM {drop_pct:.0f}%]</b> 🚨\n\n"
        f"🏪 <b>Gian hàng:</b> {seller} (🎖️ <b>Tmall Official Flagship</b>)\n"
        f"🏷️ <b>Ngành hàng:</b> {category}\n"
        f"📦 <b>Sản phẩm:</b> {title}\n\n"
        f"💰 <b>Giá sập sàn:</b> <code>{drop_price:,.0f} đ</code> <i>(Giảm sâu trực tiếp)</i>\n"
        f"📊 <b>Giá gốc niêm yết:</b> <code>{sibling_price:,.0f} đ</code>\n"
        f"📉 <b>Mức giảm:</b> <b>-{drop_pct:.1f}%</b> (Tiết kiệm <b>{save_amount:,.0f} đ</b>)\n\n"
        f"🛒 <b>Săn ngay tại Tmall:</b> <a href=\"{url}\">Bấm vào đây để xem sản phẩm</a>\n"
        f"⏰ <i>Radar quét lúc: {time_str}</i>"
    )
    return msg

def run_tmall_brands_scan_cycle(
    trigger_type: str = "manual",
    selected_category_ids: Optional[List[str]] = None,
    batch_shops_per_cycle: Optional[int] = None,
    min_drop_pct: Optional[float] = None,
    min_price_floor: Optional[float] = None,
    max_pages_per_shop: int = 1
) -> Dict[str, Any]:
    """Chạy một chu kỳ quét các gian hàng Tmall theo các nhóm ngành trọng điểm:
    1. Lấy danh sách các nhóm ngành active (Điện gia dụng, Điện tử phụ kiện, Bách hóa, Đời sống, Thời trang thể thao, Thời trang nam).
    2. Quét lần lượt từng shop trong nhóm ngành.
    3. Cào toàn bộ sản phẩm của shop (all products) và bóc tách deal sập sàn.
    4. Bắn Telegram và lưu vào database.
    """
    global _tmall_brand_scanner_status, _tmall_shop_rotation_pointer
    if _tmall_brand_scanner_status.get("is_running"):
        return {
            "status": "already_running",
            "message": "Radar quét Tmall Brand đang chạy, vui lòng đợi hoàn tất."
        }

    init_tmall_brands_tables()
    cfg = get_general_scanner_config()
    eff_min_drop = min_drop_pct if min_drop_pct is not None else float(cfg.get("tmall_min_drop_pct", cfg.get("min_drop_pct", 80.0)))
    eff_max_drop = float(cfg.get("tmall_max_drop_pct", 95.0))
    eff_min_floor = min_price_floor if min_price_floor is not None else float(cfg.get("min_price_floor", 35000.0))

    start_time = time.time()
    _tmall_brand_scanner_status.update({
        "is_running": True,
        "trigger_type": trigger_type,
        "started_at": start_time,
        "current_category_name": "",
        "current_shop_name": "",
        "current_shop_index": 0,
        "total_shops": 0,
        "items_scanned": 0,
        "deals_found": 0,
        "message": "Đang khởi động radar quét Tmall Brand..."
    })

    # Lấy các nhóm ngành active (mặc định 6 nhóm trọng điểm của user)
    active_cats = get_tmall_categories(active_only=True)
    if selected_category_ids:
        active_cats = [c for c in active_cats if c["id"] in selected_category_ids or c["name"] in selected_category_ids]

    if not active_cats:
        _tmall_brand_scanner_status["is_running"] = False
        return {"status": "error", "message": "Không có nhóm ngành Tmall nào được kích hoạt để quét."}

    # Gom danh sách toàn bộ các shop cần quét theo thứ tự nhóm ngành
    all_shops = []
    for c in active_cats:
        shops_in_cat = get_tmall_shops(category_id=c["id"], active_only=True, limit=500)
        for s in shops_in_cat:
            all_shops.append(s)

    if not all_shops:
        _tmall_brand_scanner_status["is_running"] = False
        return {"status": "error", "message": "Chưa có gian hàng nào trong các nhóm ngành được chọn."}

    # Nếu chạy định kỳ 5 phút trong nền (auto_5m), quét xoay vòng batch_shops (vd: 6 - 8 shop / chu kỳ)
    if trigger_type == "auto_5m":
        batch_size = batch_shops_per_cycle or int(cfg.get("batch_keywords_per_cycle", 6))
        start_idx = _tmall_shop_rotation_pointer % len(all_shops)
        shops_to_run = []
        for i in range(min(batch_size, len(all_shops))):
            shops_to_run.append(all_shops[(start_idx + i) % len(all_shops)])
        _tmall_shop_rotation_pointer = (start_idx + len(shops_to_run)) % len(all_shops)
    else:
        # Khi kích hoạt thủ công: nếu batch_shops_per_cycle được chỉ định thì lấy bấy nhiêu, không thì quét toàn bộ
        if batch_shops_per_cycle and batch_shops_per_cycle < len(all_shops):
            shops_to_run = all_shops[:batch_shops_per_cycle]
        else:
            shops_to_run = all_shops

    _tmall_brand_scanner_status["total_shops"] = len(shops_to_run)
    deals_found_count = 0
    items_scanned_count = 0
    now = time.time()
    day_ago = now - 86400

    try:
        for idx, shop in enumerate(shops_to_run, 1):
            s_name = shop["shop_name"]
            s_slug = shop["shop_slug"]
            c_name = shop["category_name"]

            _tmall_brand_scanner_status["current_shop_index"] = idx
            _tmall_brand_scanner_status["current_category_name"] = c_name
            _tmall_brand_scanner_status["current_shop_name"] = s_name
            _tmall_brand_scanner_status["message"] = f"Đang quét shop [{idx}/{len(shops_to_run)}]: {s_name} ({c_name})..."

            try:
                # Cào toàn bộ sản phẩm của shop
                prods = lazada.scrape_shop_all_products(s_slug, max_pages=max_pages_per_shop)
                prods = prods or []
                items_scanned_count += len(prods)
                _tmall_brand_scanner_status["items_scanned"] = items_scanned_count

                shop_deals_found = 0

                for it in prods:
                    title = it.get("title", "")
                    price_val = float(it.get("price", 0))
                    orig_val = float(it.get("orig_price", 0))
                    item_url = it.get("product_url", "")
                    image_url = it.get("image_url", "")
                    item_id = str(it.get("item_id", ""))

                    # 1. Bỏ qua nếu giá quá thấp (bẫy linh kiện / quà tặng 0đ)
                    if price_val < eff_min_floor:
                        continue

                    # 2. Tính mức giảm giá
                    if orig_val <= price_val or orig_val <= 0:
                        continue

                    drop_pct = round(((orig_val - price_val) / orig_val) * 100.0, 1)

                    # Chỉ lấy các kèo thực sự sập sàn từ 80% - 85%+ và loại trừ bẫy ảo > 95%
                    if drop_pct < eff_min_drop or drop_pct > eff_max_drop:
                        continue

                    # 3. Lọc bẫy phụ kiện
                    is_trap, trap_reason = is_accessory_trap(title, "Mặc định")
                    if is_trap:
                        continue

                    # 4. Kiểm tra trùng lặp trong 24h
                    recent = db.q("""
                        SELECT id FROM lazada_deep_drops
                        WHERE item_id = ? AND created_at > ?
                    """, (item_id, day_ago), one=True)

                    if not recent:
                        deal_data = {
                            "item_id": item_id,
                            "sku_id": item_id,
                            "product_title": title,
                            "category": c_name,
                            "variation_name": "Toàn bộ / Mặc định",
                            "sibling_count": 1,
                            "sibling_avg_price": orig_val,
                            "drop_price": price_val,
                            "drop_pct": drop_pct,
                            "stock": 10,
                            "seller_name": s_name,
                            "is_mall": 1,
                            "product_url": item_url,
                            "image_url": image_url
                        }

                        # Bắn cảnh báo Telegram
                        try:
                            tg_msg = format_tmall_brand_telegram(deal_data)
                            tg(tg_msg, parse_mode="HTML")
                        except Exception as tg_err:
                            print(f"[tmall_scanner] Lỗi gửi Telegram: {tg_err}")

                        # Lưu vào database
                        db.x("""
                            INSERT INTO lazada_deep_drops(
                                item_id, sku_id, product_title, category, variation_name,
                                sibling_count, sibling_avg_price, drop_price, drop_pct,
                                stock, seller_name, is_mall, product_url, image_url,
                                sent_to_tg, sent_to_tg_at, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """, (
                            item_id, item_id, title, c_name, "Toàn bộ / Mặc định",
                            1, orig_val, price_val, drop_pct,
                            10, s_name, 1, item_url, image_url,
                            now, now
                        ))

                        deals_found_count += 1
                        shop_deals_found += 1
                        _tmall_brand_scanner_status["deals_found"] = deals_found_count

                # Cập nhật thông số shop
                db.x("""
                    UPDATE lazada_tmall_shops
                    SET last_scanned_at = ?, last_items_count = ?, deals_found_count = deals_found_count + ?, updated_at = ?
                    WHERE id = ?
                """, (now, len(prods), shop_deals_found, now, shop["id"]))

            except Exception as shop_err:
                print(f"[tmall_scanner] Lỗi quét shop '{s_name}': {shop_err}")

            # Kiểm tra yêu cầu dừng nếu đang chạy liên tục
            if _tmall_continuous_stop_requested:
                print("[tmall_scanner] ⏹️ Nhận được tín hiệu dừng, ngắt vòng lặp shop.")
                break

            # Nghỉ ngắn giữa các shop để trình duyệt mở êm và tránh WAF
            time.sleep(random.uniform(2.0, 3.5))

        finish_time = time.time()
        final_msg = f"Đã quét xong {len(shops_to_run)} shop Tmall ({items_scanned_count} sản phẩm), phát hiện {deals_found_count} kèo sập sàn Brand."
        _tmall_brand_scanner_status.update({
            "is_running": False,
            "last_finished_at": finish_time,
            "last_result": final_msg,
            "message": final_msg
        })

        return {
            "status": "success",
            "message": final_msg,
            "shops_scanned": len(shops_to_run),
            "items_scanned": items_scanned_count,
            "deals_found": deals_found_count
        }

    except Exception as e:
        finish_time = time.time()
        err_msg = f"Lỗi chu kỳ quét Tmall Brand: {e}"
        _tmall_brand_scanner_status.update({
            "is_running": False,
            "last_finished_at": finish_time,
            "last_result": err_msg,
            "message": err_msg
        })
        return {
            "status": "error",
            "message": err_msg,
            "deals_found": deals_found_count
        }
    finally:
        _tmall_brand_scanner_status["is_running"] = False

def start_tmall_continuous_runner(
    selected_category_ids: Optional[List[str]] = None,
    min_drop_pct: Optional[float] = None,
    min_price_floor: Optional[float] = None,
    max_pages_per_shop: int = 1
) -> Dict[str, Any]:
    """Khởi động luồng quét tuần tự toàn bộ các nhóm ngành và lặp lại liên tục ngày đêm."""
    global _tmall_continuous_running, _tmall_continuous_stop_requested, _tmall_continuous_thread, _tmall_continuous_loop_count
    if _tmall_continuous_running:
        return {
            "success": False,
            "message": "Radar quét Tmall Brand tuần tự liên tục hiện đang chạy rồi!",
            "is_running": True
        }

    _tmall_continuous_stop_requested = False
    _tmall_continuous_running = True
    _tmall_brand_scanner_status["continuous_mode"] = True

    def _continuous_worker():
        global _tmall_continuous_running, _tmall_continuous_loop_count, _tmall_continuous_stop_requested
        print("[tmall_continuous_runner] 🚀 Bắt đầu tiến trình quét Tmall Brand tuần tự liên tục qua các nhóm ngành...")

        while not _tmall_continuous_stop_requested:
            _tmall_continuous_loop_count += 1
            loop_start = time.time()
            print(f"\n=======================================================")
            print(f"[tmall_continuous_runner] 🔁 BẮT ĐẦU VÒNG QUÉT TUẦN TỰ THỨ #{_tmall_continuous_loop_count}...")
            print(f"=======================================================")

            try:
                res = run_tmall_brands_scan_cycle(
                    trigger_type="continuous",
                    selected_category_ids=selected_category_ids,
                    batch_shops_per_cycle=None, # Quét tuần tự toàn bộ danh sách shop
                    min_drop_pct=min_drop_pct,
                    min_price_floor=min_price_floor,
                    max_pages_per_shop=max_pages_per_shop
                )
                print(f"[tmall_continuous_runner] ✅ Hoàn tất vòng #{_tmall_continuous_loop_count}: {res.get('message')}")
            except Exception as loop_err:
                print(f"[tmall_continuous_runner] ❌ Lỗi vòng #{_tmall_continuous_loop_count}: {loop_err}")

            if _tmall_continuous_stop_requested:
                break

            # Nghỉ 15 giây giữa các vòng quét tuần tự để làm mát tài nguyên
            print(f"[tmall_continuous_runner] ⏳ Nghỉ 15s trước khi lặp lại vòng tiếp theo...")
            for _ in range(15):
                if _tmall_continuous_stop_requested:
                    break
                time.sleep(1)

        _tmall_continuous_running = False
        _tmall_brand_scanner_status["continuous_mode"] = False
        _tmall_brand_scanner_status["message"] = "Đã dừng chế độ quét liên tục."
        print("[tmall_continuous_runner] ⏹️ Đã dừng luồng quét Tmall Brand tuần tự liên tục.")

    _tmall_continuous_thread = threading.Thread(target=_continuous_worker, daemon=True, name="TmallContinuousWorker")
    _tmall_continuous_thread.start()

    return {
        "success": True,
        "message": "🚀 Đã kích hoạt radar quét tuần tự lần lượt các nhóm ngành và lặp lại liên tục!",
        "continuous_mode": True
    }

def stop_tmall_continuous_runner() -> Dict[str, Any]:
    """Dừng luồng quét tuần tự liên tục."""
    global _tmall_continuous_stop_requested, _tmall_continuous_running
    if not _tmall_continuous_running:
        return {"success": False, "message": "Radar quét liên tục hiện không chạy."}

    _tmall_continuous_stop_requested = True
    _tmall_brand_scanner_status["message"] = "Đang yêu cầu dừng quét liên tục sau khi hoàn tất shop này..."
    return {"success": True, "message": "Đã gửi lệnh dừng quét liên tục. Hệ thống sẽ dừng sau khi cào xong shop hiện tại."}


