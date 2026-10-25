# Creates the dataset folder layout with original sample files (one-time seed).
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dataset"

FILES = {
    "grade_1/toan/textbooks/sgk_toan1_cac_so_co_hai_chu_so.txt": """\
Bài: CÁC SỐ CÓ HAI CHỮ SỐ

Yêu cầu cần đạt
- Đọc, viết các số từ 20 đến 50.
- So sánh các số có hai chữ số trong phạm vi 50.
- Nhận biết số lượng chục, đơn vị của một số có hai chữ số.

Nội dung chính
1. Đếm thêm các chục: hai mươi (20), ba mươi (30), bốn mươi (40), năm mươi (50).
2. Mỗi số có hai chữ số gồm số chục và số đơn vị. Ví dụ: 24 gồm 2 chục và 4 đơn vị.
3. So sánh số có hai chữ số: so sánh số chục trước, nếu số chục bằng nhau thì so sánh số đơn vị.
   Ví dụ: 34 < 43 vì 3 chục ít hơn 4 chục; 45 > 42 vì cùng 4 chục mà 5 đơn vị nhiều hơn 2 đơn vị.

Bài tập mẫu
Bài 1. Viết các số: hai mươi bảy, bốn mươi, ba mươi chín thành chữ số.
Bài 2. Khoanh vào số lớn nhất trong: 25, 52, 34, 43.
Bài 3. Điền dấu <, >, =: 38 … 41; 50 … 50; 29 … 92.
""",
    "grade_1/toan/lesson_plans/giao_an_cac_so_co_hai_chu_so.txt": """\
GIÁO ÁN TOÁN LỚP 1
Bài dạy: Các số có hai chữ số (trong phạm vi 50)

I. MỤC TIÊU
- Đọc, viết được các số từ 20 đến 50.
- So sánh được các số có hai chữ số trong phạm vi 50.
- Phát triển kỹ năng quan sát, so sánh; yêu thích môn Toán.

II. ĐỒ DÙNG DẠY HỌC
- Giáo viên: que tính, bó một chục, các thẻ số từ 20 đến 50.
- Học sinh: que tính, bảng con, phấn.

III. CÁC HOẠT ĐỘNG DẠY HỌC

Hoạt động 1. Khởi động (5 phút)
- Giáo viên tổ chức trò chơi "Đếm tiếp": học sinh đếm tiếp các số từ 1 đến 20.
- Giới thiệu bài, ghi đầu bài lên bảng.

Hoạt động 2. Hình thành kiến thức (12 phút)
- Giáo viên xếp 2 bó một chục và 4 que rời, hỏi: có tất cả bao nhiêu que tính?
- Hướng dẫn học sinh đếm: hai mươi mốt, hai mươi hai, ..., hai mươi bốn (24).
- Nhấn mạnh: 24 gồm 2 chục và 4 đơn vị.
- Học sinh thực hành đọc, viết số 24 và các số lân cận vào bảng con.

Hoạt động 3. Luyện tập (10 phút)
- Bài 1: Đọc và viết các số theo mẫu.
- Bài 2: So sánh các cặp số, điền dấu <, >, =.
- Giáo viên quan sát, giúp đỡ học sinh còn chậm.

Hoạt động 4. Vận dụng, trò chơi (5 phút)
- Trò chơi "Ai nhanh ai đúng": giơ thẻ số lớn hơn khi giáo viên đọc hai số.

IV. ĐÁNH GIÁ
- Giáo viên nhận xét tinh thần học tập, mức độ hoàn thành bài tập của học sinh.

PHỤ LỤC
- Đáp án bài 2: 38 < 41; 50 = 50; 29 < 92.
""",
    "grade_1/toan/worksheets/phieu_tuan_1_cac_so_hai_chu_so.txt": """\
PHIẾU BÀI TẬP TUẦN 1 – TOÁN LỚP 1
Tên bài: Các số có hai chữ số

Bài 1. Nối số với cách đọc đúng.
20 – hai mươi lăm      25 – hai mươi      52 – năm mươi hai

Bài 2. Viết số thích hợp vào chỗ chấm.
3 chục và 2 đơn vị = ……        4 chục và 7 đơn vị = ……

Bài 3. Điền dấu <, > hoặc = .
34 … 43        50 … 50        29 … 92        41 … 14

Bài 4. Khoanh vào số bé nhất.
A. 25   B. 52   C. 34   D. 43

Bài 5. Sắp xếp các số sau theo thứ tự từ bé đến lớn: 45, 18, 32, 50.

ĐÁP ÁN
Bài 1: 20 – hai mươi; 25 – hai mươi lăm; 52 – năm mươi hai.
Bài 2: 32; 47.
Bài 3: 34 < 43; 50 = 50; 29 < 92; 41 > 14.
Bài 4: A. 25.
Bài 5: 18 < 32 < 45 < 50.
""",
    "grade_1/tieng_viet/lesson_plans/giao_an_on_va_chu_o.txt": """\
GIÁO ÁN TIẾNG VIỆT LỚP 1
Bài dạy: Ôn các chữ và thanh đã học

I. MỤC TIÊU
- Đọc và viết được các chữ, tiếng chứa các âm đã học.
- Phát triển lời nói tự nhiên theo chủ đề gia đình.

II. ĐỒ DÙNG DẠY HỌC
- Giáo viên: bộ tranh ảnh chủ đề gia đình, bảng chữ.
- Học sinh: bảng con, sách giáo khoa.

III. CÁC HOẠT ĐỘNG DẠY HỌC

Hoạt động 1. Khởi động (5 phút)
- Hát và vận động theo bài "Cả nhà thương nhau".

Hoạt động 2. Ôn luyện (12 phút)
- Giáo viên chỉ bảng chữ, học sinh đồng thanh đọc.
- Học sinh tìm tiếng có chứa âm đang ôn trong sách giáo khoa.
- Viết bảng con: ba, mẹ, cá, cà.

Hoạt động 3. Luyện nói (8 phút)
- Chủ đề: Gia đình em. Gợi ý: gia đình em có những ai? Bố mẹ làm nghề gì?

IV. ĐÁNH GIÁ
- Nhận xét ability đọc, viết của học sinh; khuyến khích về nhà ôn bài.

Lưu ý: giáo viên điều chỉnh nhịp độ theo học sinh lớp mình.
""",
    "grade_2/toan/textbooks/sgk_toan2_phep_cong_khong_nho_trong_100.txt": """\
Bài: PHÉP CỘNG KHÔNG NHỚ TRONG PHẠM VI 100

Yêu cầu cần đạt
- Thực hiện được phép cộng không nhớ trong phạm vi 100 (dạng 25 + 31, 34 + 15).
- Vận dụng vào giải bài toán có lời văn đơn giản.

Nội dung chính
1. Cộng số có hai chữ số với số có hai chữ số không nhớ: cộng các đơn vị với nhau,
   cộng các chục với nhau. Ví dụ: 25 + 31 = 56 vì 5 + 1 = 6 và 2 chục + 3 chục = 5 chục.
2. Dạng 34 + 15: 4 + 5 = 9; 3 chục + 1 chục = 4 chục; kết quả 49.
3. Bài toán có lời văn: đọc kĩ đề, xác định số đã cho, phép tính phải dùng.

Bài tập mẫu
Bài 1. Đặt tính rồi tính: 42 + 36; 51 + 27.
Bài 2. Lan có 32 quyển vở, Huệ có nhiều hơn Lan 14 quyển vở. Hỏi Huệ có bao nhiêu quyển vở?
""",
    "grade_2/toan/lesson_plans/giao_an_phep_cong_khong_nho.txt": """\
GIÁO ÁN TOÁN LỚP 2
Bài dạy: Phép cộng không nhớ trong phạm vi 100

I. MỤC TIÊU
- Thực hiện được phép cộng hai số có hai chữ số không nhớ trong phạm vi 100.
- Giải được bài toán có lời văn liên quan đến phép cộng.
- Yêu thích môn Toán, chăm chỉ làm bài.

II. ĐỒ DÙNG DẠY HỌC
- Giáo viên: que tính thành bó chục, bảng phụ ghi sẵn phép tính mẫu.
- Học sinh: que tính, bảng con.

III. CÁC HOẠT ĐỘNG DẠY HỌC

Hoạt động 1. Khởi động (5 phút)
- Ôn phép cộng trong phạm vi 20 qua trò chơi "Chuyền bóng toán học".

Hoạt động 2. Hình thành kiến thức (12 phút)
- Giáo viên đặt bài toán: có 2 bó một chục và 5 que tính, thêm 3 bó một chục và 1 que tính.
- Hướng dẫn đặt tính cột dọc: đơn vị thẳng cột với đơn vị, chục thẳng cột với chục.
- Học sinh tính: 25 + 31 = 56, nêu cách tính (cộng đơn vị, cộng chục).

Hoạt động 3. Luyện tập thực hành (10 phút)
- Bài 1: Đặt tính rồi tính 42 + 36, 51 + 27.
- Bài 2: Giải bài toán về vở của Lan và Huệ (32 + 14 = 46 quyển vở).
- Chữa bài chung, nhắc học sinh trình bày đầy đủ câu lời giải.

Hoạt động 4. Củng cố (5 phút)
- Trò chơi "Ai tính nhanh": thi tính nhẩm các phép cộng tròn chục.

IV. ĐÁNH GIÁ
- Đánh giá qua bài làm trên bảng con; khen ngợi học sinh tiến bộ.

PHỤ LỤC
- Đáp án: 42 + 36 = 78; 51 + 27 = 78; Huệ có 46 quyển vở.
""",
}

METAS = {
    "grade_1/toan/textbooks/sgk_toan1_cac_so_co_hai_chu_so.txt": {
        "grade": "grade_1", "subject": "toan", "book_series": "Kết nối tri thức",
        "lesson": "Các số có hai chữ số", "doc_type": "textbook",
    },
    "grade_1/toan/lesson_plans/giao_an_cac_so_co_hai_chu_so.txt": {
        "grade": "grade_1", "subject": "toan", "book_series": "Kết nối tri thức",
        "lesson": "Các số có hai chữ số", "doc_type": "lesson_plan",
    },
    "grade_1/toan/worksheets/phieu_tuan_1_cac_so_hai_chu_so.txt": {
        "grade": "grade_1", "subject": "toan", "book_series": "Kết nối tri thức",
        "lesson": "Tuần 1", "doc_type": "worksheet",
    },
    "grade_1/tieng_viet/lesson_plans/giao_an_on_va_chu_o.txt": {
        "grade": "grade_1", "subject": "tieng_viet", "book_series": "Chân trời sáng tạo",
        "lesson": "Ôn các chữ và thanh đã học", "doc_type": "lesson_plan",
    },
    "grade_2/toan/textbooks/sgk_toan2_phep_cong_khong_nho_trong_100.txt": {
        "grade": "grade_2", "subject": "toan", "book_series": "Kết nối tri thức",
        "lesson": "Phép cộng không nhớ trong phạm vi 100", "doc_type": "textbook",
    },
    "grade_2/toan/lesson_plans/giao_an_phep_cong_khong_nho.txt": {
        "grade": "grade_2", "subject": "toan", "book_series": "Kết nối tri thức",
        "lesson": "Phép cộng không nhớ trong phạm vi 100", "doc_type": "lesson_plan",
    },
}

TEMPLATES = {
    "format_templates/lesson_plan.json": {
        "doc_type": "lesson_plan",
        "title": "GIÁO ÁN {subject_upper} LỚP {grade_num}",
        "sections": [
            {"id": "header", "type": "kv_pairs", "label": "Bài dạy", "fields": ["lesson", "duration"]},
            {"id": "objectives", "type": "bullets", "label": "I. MỤC TIÊU"},
            {"id": "materials", "type": "bullets", "label": "II. ĐỒ DÙNG DẠY HỌC"},
            {"id": "activities", "type": "activities", "label": "III. CÁC HOẠT ĐỘNG DẠY HỌC",
             "activity_fields": ["teacher", "students"]},
            {"id": "assessment", "type": "text", "label": "IV. ĐÁNH GIÁ"},
            {"id": "appendix", "type": "text", "label": "PHỤ LỤC", "optional": True},
        ],
    },
    "format_templates/worksheet.json": {
        "doc_type": "worksheet",
        "title": "PHIẾU BÀI TẬP TUẦN {week} – {subject_upper} LỚP {grade_num}",
        "sections": [
            {"id": "exercises", "type": "exercises", "label": "BÀI TẬP"},
            {"id": "answers", "type": "text", "label": "ĐÁP ÁN"},
        ],
    },
}


def main() -> None:
    for rel, content in FILES.items():
        path = BASE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        meta = METAS[rel]
        (BASE / (rel + ".meta.json")).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    for rel, content in TEMPLATES.items():
        path = BASE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seeded {len(FILES)} sample files + {len(TEMPLATES)} format templates into {BASE}")


if __name__ == "__main__":
    main()
