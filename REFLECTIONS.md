# Reflections — costctl W6 Side Challenge

## 1. Multi-account: chạy costctl trên 100 AWS accounts

Hiện tại `costctl` dùng credentials mặc định của boto3 — chỉ nói chuyện được với 1 account tại 1 thời điểm.

Để scale lên 100 accounts:
- Lưu danh sách account ID + IAM role ARN vào config file hoặc SSM Parameter Store
- Với mỗi account, gọi `sts.assume_role()` để lấy credentials tạm thời, sau đó tạo `boto3.Session` mới với credentials đó
- Chạy logic lệnh bên trong session đó
- Gộp output thành CSV có thêm cột `account_id` để nhìn được cost/resource theo từng account

Phần khó nhất là IAM: mỗi account cần có 1 role trust account "orchestrator" để assume vào. Đây là pattern cross-account role chuẩn trong AWS Organizations.

---

## 2. `idle` vs Trusted Advisor

`costctl idle` kiểm tra CPU trung bình trong 24 giờ qua.
AWS Trusted Advisor kiểm tra CPU trong 14 ngày qua.

**Tin `idle` hơn khi:**
- Resource mới tạo, TA chưa có đủ 14 ngày data
- Cần kiểm tra ngay lập tức (TA chỉ refresh 1 lần/tuần với free tier)
- Muốn scan nhanh trước khi demo hoặc cuối sprint để dọn dẹp

**Tin Trusted Advisor hơn khi:**
- Cần nhìn pattern dài hạn — EC2 dev có thể idle cuối tuần nhưng chạy nặng ngày thường, `idle` sẽ false positive nếu chạy vào Chủ nhật
- Muốn có xác nhận thêm trước khi terminate thứ quan trọng
- Đang làm cost review chính thức, không phải cleanup nhanh

Thực tế: dùng `idle` để scan lần đầu, xác nhận lại với TA trước khi thật sự terminate.

---

## 3. `clean --apply` blast radius

Nếu vô tình chạy:
```bash
./costctl.py clean --tag Environment=dev --apply
```
trên account dùng chung — toàn bộ EC2 và EBS volume có tag `Environment=dev` bị xóa ngay lập tức, kể cả resource của các team khác đang dùng chung account đó.

**Những thứ cần có để giới hạn thiệt hại:**

1. **Confirmation với danh sách resource** — in ra từng resource ID sẽ bị xóa và hỏi `"Sắp terminate N resource — gõ YES để xác nhận"` trước khi làm bất cứ điều gì
2. **IAM policy scoping** — giới hạn `ec2:TerminateInstances` chỉ với resource có thêm tag `Owner=<team>`, tránh đụng vào resource của team khác
3. **CloudTrail logging** — mọi API call đều được log kèm IAM identity, biết được ai chạy lệnh gì lúc nào
4. **Snapshot tự động** — tạo EBS snapshot trước khi xóa volume để có thể khôi phục
5. **Soft-delete / grace period** — stop instance trước, chờ 24h rồi mới terminate — có thời gian phát hiện và cancel nếu nhầm
