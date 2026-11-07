# examples: โค้ดตัวอย่างที่ไม่ขึ้นกับใคร

โค้ด Python ที่เขียนขึ้นเอง ใช้แค่ stdlib ไม่มีโค้ดหรือชื่อของบริษัทใด และไม่ต้องมี Django แต่ละโฟลเดอร์คือ 1 กรณีทดสอบ:

```
examples/<ชื่อ>/
  case.json      ชื่อ, รูปร่าง (shape), โมดูลเดิม, scenarios, งาน (tasks), กิ่งที่ไม่มีใครเรียก (kept_branches), ผลที่ควรได้
  src/           โปรเจกต์ตัวอย่าง (นี่คือ import root)
  scenarios.py   สถานการณ์สำหรับ parity.py
```

| ตัวอย่าง | shape | ทดสอบอะไร | ผลที่ควรได้ |
|---|---|---|---|
| `orders` | refactor | โมดูลเดียวที่มี 4 ขั้นตอนของ flow เดียว, helper ซ้อน 2 ชั้น, 3 flag ที่ไม่มีใครส่ง, ก้อนที่ซ้ำทั้งก้อนใน flow เดียว, ฟังก์ชัน pure ที่หลายขั้นตอนเรียก | แยกเป็นไฟล์ละงาน + `shared.py`, parity ว่าง; มี `golden/` เป็นเฉลยที่ถูก |
| `statements` | refactor | class ที่ส่งงานผ่าน `self.rows` + subclass 1 ชั้น | `--check` ต้องไม่รายงาน state ผ่าน `self` หลัง rewrite |
| `clean` | no-change | โค้ดที่อ่านง่ายอยู่แล้ว | Map ไม่เสนอการย้ายใดๆ แล้วหยุด |
| `plugins` | list-by-hand | เรียก handler ด้วยชื่อตอนรัน (`getattr`) | ผู้ใช้ skill ต้องไล่ handler เองใน `map.md` และบอกที่ประตู |
| `async_jobs` | unsupported | `async def` ที่ `await` | ประตู Map บอกว่า 1.x ไม่รองรับ แล้วหยุด |

เมื่อรองรับ async ใน 1.2 ให้เปลี่ยน `async_jobs` เป็น `refactor` (และสลับคู่ข้อจำกัดใน `tests/`)
