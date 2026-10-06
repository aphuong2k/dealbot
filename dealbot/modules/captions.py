"""Module 2b: AI viết nhiều biến thể caption, mỗi group một giọng."""
import os, re, json, anthropic

ANGLES = ["chia sẻ kinh nghiệm cá nhân", "cảnh báo sắp hết deal", "so sánh giá nhanh",
          "gợi ý cho người đang tìm mua", "ngắn gọn kiểu nhắn bạn bè"]

def variants(deal, n=4, link_in_comment=True):
    suffix = 'Link minh de o comment nha!' if link_in_comment else ''
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            cli = anthropic.Anthropic(api_key=api_key)
            prompt = f"""Viết {n} biến thể bài đăng Facebook tiếng Việt cho sản phẩm sau, mỗi biến thể một góc: {ANGLES[:n]}.
Sản phẩm: {deal['title']} | giá {deal['price']:,.0f}đ | giảm {deal['discount']:.0f}% | {deal['rating']}★ | đã bán {deal['sold']}
Yêu cầu: giọng người thật, không văn mẫu quảng cáo, không phóng đại, không hứa hẹn sai sự thật, 2-4 câu, tối đa 1-2 emoji,
{'KHÔNG chèn link trong bài, cuối bài ghi \"link mình để ở comment\"' if link_in_comment else 'link sẽ được thêm sau'}.
Trả JSON array gồm {n} chuỗi, không giải thích."""
            msg = cli.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=1200,
                                      messages=[{"role": "user", "content": prompt}])
            return json.loads(re.search(r"\[.*\]", msg.content[0].text, re.S).group(0))
        except Exception as e:
            print("[captions] Claude API fallback:", type(e).__name__)

    # Mẫu dự phòng tự nhiên
    price_str = f"{deal['price']:,.0f}đ"
    title = deal['title']
    cmt_vn = 'Link mình để ở comment nha!' if link_in_comment else ''
    return [
        f"Vừa lướt thấy mã {title} đang sale sốc còn {price_str} (giảm {deal['discount']:.0f}%). Bác nào đang cần thì tranh thủ nha. {cmt_vn}".strip(),
        f"Em này được đánh giá {deal['rating']}★, thấy bán được hơn {deal['sold']} chiếc rồi. Giá hôm nay giảm sâu còn {price_str} thôi. {cmt_vn}".strip(),
        f"Deal ngon trong ngày cho ai cần tìm {title}, giá tụt còn {price_str}. Đặt sớm kẻo hết sale. {cmt_vn}".strip(),
        f"Chia sẻ cho cả nhà mã {title} giá cực hời chỉ {price_str}. {cmt_vn}".strip()
    ][:n]


