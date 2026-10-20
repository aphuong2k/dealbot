"""
Config-Driven Category Mapping & Matcher cho Dealbot
Dựa trên kiến trúc chuẩn từ auto-aff để khớp Deal hời ↔ Group Facebook chính xác 100%.
"""
from typing import Dict, List, Optional, Tuple
import random
import re

CATEGORY_RULES: List[Dict] = [
    {
        "category_name": "Thiết Bị Điện Tử",
        "aliases": ["Điện Thoại & Phụ Kiện", "Máy Tính & Phụ Kiện", "Consumer Electronics", "Mobile & Gadgets", "Computer & Accessories", "đồ công nghệ giá rẻ", "công nghệ"],
        "group_keywords": ["iphone", "apple", "công nghệ", "điện tử", "tai nghe", "điện thoại", "android", "linh kiện", "setup", "phím cơ", "gaming", "keycap", "chuột", "laptop", "pc", "tin học"],
        "deal_keywords": ["điện tử", "điện thoại", "tai nghe", "bàn phím", "chuột", "laptop", "cáp", "sạc", "loa", "công nghệ", "pin", "cường lực", "ốp lưng", "bluetooth", "phím cơ"],
        "deal_query_like": ["%công nghệ%", "%điện tử%", "%điện thoại%", "%máy tính%"],
        "sub_categories": {
            "iphone": {
                "group_keywords": ["iphone", "apple"],
                "deal_name_like": ["%iphone%", "%apple%", "%airpod%", "%ốp lưng%"]
            },
            "phim_co": {
                "group_keywords": ["phím cơ", "keycap", "bàn phím"],
                "deal_name_like": ["%phím%", "%keycap%", "%switch%", "%bàn phím%"]
            }
        }
    },
    {
        "category_name": "Thời Trang Nam",
        "aliases": ["Men Clothes", "thời trang nam", "nam"],
        "group_keywords": ["đồ nam", "quần nam", "áo nam", "thời trang nam", "owen", "aristino", "nam béo", "phối đồ nam", "nam", "men", "mặc đẹp nam"],
        "deal_keywords": ["nam", "áo nam", "quần nam", "sơ mi", "polo", "khoác nam", "ví nam", "thắt lưng", "giày nam", "boxer", "sịp"],
        "deal_query_like": ["%Thời Trang Nam%", "%nam%"]
    },
    {
        "category_name": "Thời Trang Nữ",
        "aliases": ["Women Clothes", "thời trang nữ", "thời trang", "nữ"],
        "group_keywords": ["đồ nữ", "quần nữ", "áo nữ", "váy", "nữ", "women", "xinh", "chị em", "làm đẹp", "mặc đẹp", "nấm lùn", "1m50", "genz", "tips phối đồ", "đầm", "outfit", "bánh bèo", "thời trang nữ"],
        "deal_keywords": ["nữ", "váy", "đầm", "áo nữ", "quần nữ", "chân váy", "set đồ nữ", "túi xách", "croptop", "cardigan", "bra", "búp bê"],
        "deal_query_like": ["%Thời Trang Nữ%", "%nữ%"]
    },
    {
        "category_name": "Nhà Cửa & Đời Sống",
        "aliases": ["Thiết Bị Điện Gia Dụng", "Gia Dụng", "Home Appliances", "Home & Living", "gia dụng"],
        "group_keywords": ["gia dụng", "nhà cửa", "nội thất", "bếp", "nồi", "nghiện nhà", "yêu bếp", "decor", "tiện ích"],
        "deal_keywords": ["gia dụng", "bếp", "nồi", "chảo", "hộp", "kệ", "dọn dẹp", "lau nhà", "đèn", "decor", "thông minh", "nước giặt", "xả vải", "nước tẩy", "tẩy rửa"],
        "deal_query_like": ["%gia dụng%", "%nhà cửa%", "%nội thất%"]
    },
    {
        "category_name": "Sắc Đẹp & Mỹ Phẩm",
        "aliases": ["Sắc Đẹp", "Mỹ Phẩm", "Beauty & Personal Care", "Làm Đẹp", "mỹ phẩm"],
        "group_keywords": ["mỹ phẩm", "skincare", "makeup", "son", "kem", "serum", "dưỡng", "chăm sóc da", "làm đẹp", "beauty", "beautytips"],
        "deal_keywords": ["son", "kem", "serum", "dưỡng", "sữa rửa mặt", "toner", "tẩy trang", "chống nắng", "mặt nạ", "phấn", "bodymist", "nước hoa"],
        "deal_query_like": ["%mỹ phẩm%", "%sắc đẹp%", "%skincare%"]
    },
    {
        "category_name": "Mẹ & Bé",
        "aliases": ["Moms, Kids & Babies", "mẹ và bé", "mẹ bé"],
        "group_keywords": ["mẹ bỉm", "mẹ và bé", "sơ sinh", "bỉm", "tã", "sữa bột", "trẻ em", "nuôi con", "mẹ bé"],
        "deal_keywords": ["bỉm", "tã", "sữa", "bình sữa", "yếm", "đồ chơi", "sơ sinh", "mẹ bé", "xe đẩy", "núm ti"],
        "deal_query_like": ["%mẹ%bé%", "%mẹ và bé%"]
    },
    {
        "category_name": "Thể Thao & Dã Ngoại",
        "aliases": ["Thể Thao", "Dã Ngoại", "Sports & Outdoors", "thể thao & dã ngoại"],
        "group_keywords": ["thể thao", "gym", "chạy bộ", "camping", "dã ngoại", "yoga", "cầu lông", "bóng đá"],
        "deal_keywords": ["thể thao", "gym", "chạy bộ", "camping", "dã ngoại", "yoga", "bình nước", "vợt", "bóng", "găng tay"],
        "deal_query_like": ["%thể thao%"]
    }
]

GENERAL_DEAL_RULE = {
    "category_name": "Săn Deal Tổng Hợp",
    "aliases": ["Cộng Đồng Chung", "dealhunt", "săn sale", "săn sale shopee", "hội săn deal giá rẻ"],
    "group_keywords": ["săn deal", "voucher", "khuyến mãi", "khuyến mại", "giảm giá", "chợ", "rải link", "cháy túi", "flash sale", "mã giảm", "săn sale", "hội săn deal", "shopee"]
}

class CategoryMatcher:
    """Engine tìm deal phù hợp nhất với nhóm Facebook theo ngành hàng."""
    def __init__(self, rules: Optional[List[Dict]] = None):
        self._rules = rules or CATEGORY_RULES
        self._general = GENERAL_DEAL_RULE

    def match_group(self, group_cat: str, group_name: str = "") -> Dict:
        name_lower = (group_name or "").lower()
        cat_clean = (group_cat or "").strip()

        # 1. Khớp chính xác category_name hoặc alias
        for rule in self._rules:
            if cat_clean.lower() == rule["category_name"].lower():
                return {"rule": rule, "matched_by": "category"}
            if any(cat_clean.lower() == a.lower() for a in rule.get("aliases", [])):
                return {"rule": rule, "matched_by": "alias"}

        # 2. Khớp từ khóa trong tên nhóm
        for rule in self._rules:
            if any(kw in name_lower for kw in rule.get("group_keywords", [])):
                return {"rule": rule, "matched_by": "keyword"}

        # 3. Khớp từ khóa trong category/niche của nhóm
        for rule in self._rules:
            if any(kw in cat_clean.lower() for kw in rule.get("group_keywords", [])):
                return {"rule": rule, "matched_by": "keyword"}

        # 4. Fallback về săn deal tổng hợp
        return {"rule": self._general, "matched_by": "general"}

    def find_best_deal_for_group(self, group: Dict, db_mod) -> Optional[Dict]:
        """
        Tìm deal phù hợp nhất trong CSDL cho nhóm cụ thể.
        Ưu tiên:
        1. Khớp chuẩn xác theo Niche của Deal (bao gồm cả Aliases của ngành hàng)
        2. Khớp từ khóa trong Tiêu đề Deal (Deal Title Keywords)
        3. Fallback: Deal hời điểm cao nhất toàn hệ thống
        """
        g_name = (group.get("name") or "").strip()
        g_niche = (group.get("niche") or "").strip()
        g_kind = (group.get("kind") or "").strip()

        match = self.match_group(g_niche, g_name)
        rule = match["rule"]

        # Nếu là nhóm Săn Deal Tổng Hợp hoặc kind='dealhunt'
        if match["matched_by"] == "general" or g_kind == "dealhunt":
            deals = db_mod.q("""
                SELECT * FROM deals 
                WHERE is_valid = 1 
                ORDER BY score DESC, sold DESC 
                LIMIT 15
            """)
            if deals:
                return dict(random.choice(deals))
            return None

        # Thu thập danh sách tên ngành hàng & alias hợp lệ cho rule này
        target_niches = [rule["category_name"].lower()] + [a.lower() for a in rule.get("aliases", [])]
        if g_niche and g_niche.lower() not in target_niches:
            target_niches.append(g_niche.lower())
        target_niches = list(dict.fromkeys(target_niches))

        # Thử 1: Khớp chuẩn xác theo Niche của Deal trong Database
        placeholders = ", ".join(["?" for _ in target_niches])
        niche_deals = db_mod.q(f"""
            SELECT * FROM deals 
            WHERE is_valid = 1 AND LOWER(niche) IN ({placeholders})
            ORDER BY score DESC, sold DESC LIMIT 15
        """, tuple(target_niches))
        if niche_deals:
            return dict(random.choice(niche_deals))

        # Thử 2: Khớp từ khóa trong title deal
        deal_kws = rule.get("deal_keywords", [])
        if deal_kws:
            kw_conditions = " OR ".join(["LOWER(title) LIKE ?" for _ in deal_kws[:10]])
            kw_args = [f"%{k.lower()}%" for k in deal_kws[:10]]
            kw_deals = db_mod.q(f"""
                SELECT * FROM deals 
                WHERE is_valid = 1 AND ({kw_conditions})
                ORDER BY score DESC, sold DESC LIMIT 15
            """, tuple(kw_args))
            if kw_deals:
                return dict(random.choice(kw_deals))

        # Thử 3: Fallback lấy deal điểm cao nhất trong kho
        fallback_deals = db_mod.q("""
            SELECT * FROM deals 
            WHERE is_valid = 1 
            ORDER BY score DESC, created_at DESC LIMIT 15
        """)
        if fallback_deals:
            return dict(random.choice(fallback_deals))

        return None
