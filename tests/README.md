# tests: ตัวสคริปต์ทดสอบตัวเอง

ไม่ต้องติดตั้งอะไร (Python 3.10+ และ `unittest` ของ stdlib) รันที่ราก repo:

```bash
python -m unittest discover -s tests
```

| ไฟล์ | ทดสอบอะไร |
|---|---|
| `test_jump_depth.py` | ความลึก, กฎการเรียงไฟล์ (helper ใต้ผู้เรียก, `shared.py`, facade), hidden import, `--callers`, `--exclude`, `--forbid`, state ผ่าน `self` |
| `test_parity.py` | บันทึก/เทียบ, ปฏิเสธโค้ด async, ค่าคงที่จากซอร์ส, เวลา/uuid ถูกแช่แข็ง, stdlib ฝั่งเครือข่ายถูก stub, `.pure()`, decorator ของ task, `coverage` |
| `test_grade.py` | ตัวตรวจ `eval/grade.py`: เฉลยที่ถูก (`examples/orders/golden`) ต้องผ่านครบ และเฉลยที่ถูกทำให้ผิดทีละแบบต้องล้มเฉพาะข้อที่ควรล้ม |
| `test_examples.py` | รูปร่างของแต่ละ `examples/*`: ตัวอย่างต้องบันทึกซ้ำได้ผลเดิม (ยกเว้น shape `unsupported` ที่ต้องถูกปฏิเสธ), ไม่มีคำที่บ่งบอกโค้ดบริษัท |

## ข้อจำกัดที่รู้แล้ว (ตรึงไว้ทั้ง 2 ทาง)

ชื่อ `test_known_limit_*` ตรึงพฤติกรรมปัจจุบันของ 1.x คู่กับ `@unittest.expectedFailure` ที่เป็นพฤติกรรมที่ต้องการ
วันที่แก้สคริปต์แล้ว ข้อ `expectedFailure` จะ "ผ่านโดยไม่คาดคิด" ให้สลับคู่นั้น

| ข้อจำกัด | ที่ตรึงไว้ |
|---|---|
| `getattr(stubbed_module, name, None)` ไม่เคยได้ `None` ทำให้กิ่ง "ไม่พบ" ถึงไม่ได้ | `test_parity.KnownLimits` |
| เรียกด้วยชื่อตอนรัน: แผนที่มองไม่เห็นตัวที่ถูกเรียก `--check` จึงบอก OK | `test_examples.Shapes` |
| ไฟล์ `tests.py` แบบ Django นับเป็นผู้เรียกฝั่ง production | `test_jump_depth.KnownLimits` |

ใช้ `READABLE_SCRIPTS=/path/to/scripts` ถ้าสคริปต์ไม่ได้อยู่ที่ `../scripts`
