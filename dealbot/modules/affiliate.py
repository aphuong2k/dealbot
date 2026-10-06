"""Module quản lý affiliate link & gắn Sub-ID theo dõi chuyển đổi.
Giúp biết chính xác nhóm nào, nick nào, góc caption nào ra đơn và click thật.
"""
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

def sanitize_tag(s, max_len=25):
    """Làm sạch chuỗi ký tự để gắn vào query param / sub-id an toàn."""
    if not s:
        return "none"
    # Giữ lại chữ cái, số, gạch dưới, gạch ngang
    clean = re.sub(r"[^\w\-]", "", str(s))
    return clean[:max_len] if clean else "none"

def extract_group_tag(group_url):
    """Trích xuất slug hoặc id của group Facebook từ URL."""
    if not group_url:
        return "direct"
    m = re.search(r"groups/([\w.\-]+)", group_url)
    if m:
        return sanitize_tag(m.group(1), max_len=20)
    return "group"

def build_subid_link(raw_url, account="nick", group_url="", item_id="item", angle="deal", network="accesstrade"):
    """
    Gắn các tham số Sub-ID và UTM vào link affiliate.
    Hỗ trợ:
      - Accesstrade: sub1, sub2, sub3, sub4
      - Shopee Aff / Deeplink: sub_id1, sub_id2, sub_id3
      - Chuẩn chung UTM: utm_source, utm_medium, utm_campaign, utm_content
    
    Trả về: (final_url, sub_id_code)
    """
    if not raw_url:
        return "", ""

    acc_tag = sanitize_tag(account, 15)
    grp_tag = extract_group_tag(group_url)
    itm_tag = sanitize_tag(item_id, 20)
    ang_tag = sanitize_tag(angle, 15)

    composite_sub_id = f"{acc_tag}__{grp_tag}__{itm_tag}__{ang_tag}"

    parsed = urlparse(raw_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # Gắn theo quy ước Accesstrade
    query_params["sub1"] = acc_tag
    query_params["sub2"] = grp_tag
    query_params["sub3"] = itm_tag
    query_params["sub4"] = ang_tag

    # Gắn theo quy ước Shopee Affiliate
    query_params["sub_id1"] = acc_tag
    query_params["sub_id2"] = grp_tag
    query_params["sub_id3"] = itm_tag

    # Gắn UTM tiêu chuẩn
    query_params["utm_source"] = "dealbot"
    query_params["utm_medium"] = acc_tag
    query_params["utm_campaign"] = grp_tag
    query_params["utm_content"] = itm_tag

    new_query = urlencode(query_params)
    final_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

    return final_url, composite_sub_id
