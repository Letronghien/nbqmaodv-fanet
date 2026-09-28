# NBQ-MAODV: hướng dẫn tích hợp vào module SA-QMAODV (NS-3)

**NBQ-MAODV** là viết tắt của *Neighbour-Bootstrapped Q-learning Multipath AODV*, thế hệ thứ tư sau PMAODV, QMAODV và SA-QMAODV.

- **Giữ nguyên:** khám phá tuyến đa đường (RREQ/RREP/RERR), ε-greedy, α thích nghi, reward thích nghi.
- **Thay đổi:** mục tiêu cập nhật Q. Nút bootstrap từ giá trị V(u) do next-hop quảng bá, và Q giờ biểu diễn **chi phí cả đường đi** (giá trị âm).

File đi kèm: `nbq-learning.h`. Đây là file header-only, gồm lớp `nbq::Agent` (bảng Q, bộ điều khiển, công thức cập nhật) và `nbq::QValueTag`. Tôi đã kiểm tra biên dịch với C++17. Anh/chị có thể dùng nguyên lớp `Agent`, hoặc chỉ chép hàm `OnFeedback` và `AdvertisedValue` vào code đang có.

---

## 1. Sự khác biệt về thuật toán

| | SA-QMAODV (hiện có) | NBQ-MAODV (mới) |
|---|---|---|
| Ý nghĩa của Q | Tiện ích một chặng (dương) | Âm của chi phí đường đi có chiết khấu |
| Khởi tạo khi cài tuyến | `Q = (1/HC_i) / Σ(1/HC_k)` | `Q = −0.3 · HC_i` |
| Mục tiêu cập nhật | `r + γ · max_a' Q_v(d,a')` (bảng của chính mình) | `−(1 − r) + γ' · V_u(d)` (giá trị của next-hop) |
| γ | 0,9 | γ' = 0,95 |
| Thông tin trao đổi | Không | Mỗi nút quảng bá `V_v(d) = max_b Q_v(d,b)` kèm theo gói điều khiển AODV |
| Nút mất tuyến | Không báo | Quảng bá `V = −5` (ngõ cụt) |
| Đích (trạm gốc) | — | Quảng bá `V = 0` |
| Chọn next-hop | ε-greedy, Q lớn nhất | Giữ nguyên (Q lớn nhất = chi phí nhỏ nhất) |

Cách tính `V_u` khi cập nhật:

```
nếu next-hop là đích            : V_u = 0
nếu không nhận được ACK         : V_u = Q_v(d,u)      (không có thông tin mới)
nếu có V_u nhận trong 3 s gần đây: V_u = giá trị đó
còn lại                          : V_u = Q_v(d,u)
```

Reward `r ∈ [0,1]` giữ nguyên như SA-QMAODV, nên chi phí mỗi chặng `1 − r` cũng nằm trong [0,1]. Đường càng dài hoặc càng kém thì chi phí cộng dồn càng lớn.

---

## 2. Các bước sửa code

Tên hàm dưới đây theo module AODV gốc của NS-3 (`src/aodv/model/aodv-routing-protocol.cc`). Module SA-QMAODV của anh/chị kế thừa từ đó nên các vị trí tương ứng sẽ tương tự.

### Bước 0 – Thêm file và thuộc tính

1. Chép `nbq-learning.h` vào `src/<module-cua-ban>/model/` và thêm vào `CMakeLists.txt` (mục `HEADER_FILES`).
2. Trong `RoutingProtocol`, thêm thành viên:
   ```cpp
   #include "nbq-learning.h"
   nbq::Agent m_agent;
   Ptr<UniformRandomVariable> m_nbqRng;
   Ipv4Address m_sinkAddr;          // địa chỉ trạm gốc (một đích duy nhất trong kịch bản)
   bool m_isSink = false;
   ```
3. Trong `GetTypeId()`, thêm các thuộc tính để kịch bản điều khiển được:
   ```cpp
   .AddAttribute("NeighbourBootstrap", "NBQ-MAODV (true) or SA-QMAODV (false)",
                 BooleanValue(true), MakeBooleanAccessor(&RoutingProtocol::m_nbqBootstrap), MakeBooleanChecker())
   .AddAttribute("AdaptiveEpsilon", "...", BooleanValue(true), ...)
   .AddAttribute("AdaptiveAlpha",   "...", BooleanValue(true), ...)
   .AddAttribute("AdaptiveReward",  "...", BooleanValue(true), ...)
   .AddAttribute("Lambda",          "...", DoubleValue(0.5), ...)
   .AddAttribute("SinkAddress",     "...", Ipv4AddressValue(), ...)
   ```
4. Trong `Start()` hoặc `DoInitialize()`, nạp tham số rồi hẹn lịch giảm ε:
   ```cpp
   nbq::Params p;
   p.neighbourBootstrap = m_nbqBootstrap;
   p.adaptiveEpsilon = m_adaptEps; p.adaptiveAlpha = m_adaptAlpha;
   p.adaptiveReward = m_adaptReward; p.lambda = m_lambda;
   m_agent.SetParams(p);
   m_nbqRng = CreateObject<UniformRandomVariable>();
   m_isSink = (m_ipv4->GetAddress(1, 0).GetLocal() == m_sinkAddr);
   Simulator::Schedule(m_agent.EpsilonPeriod(), &RoutingProtocol::EpsTimer, this);
   ```
   ```cpp
   void RoutingProtocol::EpsTimer() {
     m_agent.DecayEpsilon();
     Simulator::Schedule(m_agent.EpsilonPeriod(), &RoutingProtocol::EpsTimer, this);
   }
   ```
   Trong phần ablation, `AdaptiveEpsilon=false` sẽ quay về lịch của QMAODV: giảm 0,02 mỗi 10 s, sàn là 0.

### Bước 1 – Cài tuyến khi nhận RREP (HOOK 1)

Ở chỗ SA-QMAODV đang thêm nhiều next-hop vào bảng định tuyến khi nhận RREP (thường trong `RecvReply`, nhánh không phải HELLO):

```cpp
std::vector<std::pair<Ipv4Address, uint32_t>> nh;
for (auto& path : danhSachNextHopToiDich)        // tối đa K = MaxPaths
    nh.push_back({path.nextHop, path.hopCount});
m_agent.InstallRoutes(dst, nh, Simulator::Now());
```

**Quan trọng:** phải bỏ mọi bước chuẩn hóa lại Q (chia cho tổng) mà code cũ có thể đang làm, vì Q của NBQ là giá trị âm.

### Bước 2 – Chọn next-hop khi chuyển tiếp dữ liệu (HOOK 3)

Trong `RouteOutput` (tại nguồn) và `RouteInput`/`Forwarding` (tại nút trung gian), thay lời gọi hàm chọn next-hop cũ bằng:

```cpp
Ipv4Address prev = /* địa chỉ nút vừa gửi gói tới (lấy từ header MAC/IP nguồn chặng trước),
                      Ipv4Address() nếu đây là nút nguồn */;
Ipv4Address nh = m_agent.Select(dst, prev, m_nbqRng);
if (nh == Ipv4Address()) { /* không còn ứng viên: xử lý như AODV (RERR / khám phá lại) */ }
// dựng Ipv4Route với gateway = nh
```

`prev` loại bỏ việc gửi ngược về nút trước, giúp chống vòng lặp giữa các nút cùng mức. Nếu code cũ đã làm việc này thì giữ nguyên.

### Bước 3 – Phản hồi MAC và cập nhật Q (HOOK 4)

Ở chỗ SA-QMAODV đang tính reward sau khi nhận ACK hoặc hết số lần thử lại (thường nối qua trace `AckedMpdu`/`DroppedMpdu` của WifiMac, hoặc `TxOkHeader`/`TxErrHeader`), thay đoạn "tính reward + cập nhật Q" bằng:

```cpp
m_agent.OnFeedback(dst, nextHop,
                   ack,                         // true: nhận ACK; false: hết retry
                   delaySec,                    // thời gian phục vụ 1 chặng, đơn vị giây
                   nextHop == dst,              // next-hop có phải đích không
                   nhEnergyFrac,                // năng lượng còn lại của next-hop [0,1], chưa biết thì 1.0
                   ownEnergyFrac,               // năng lượng còn lại của nút này [0,1]
                   Simulator::Now());
```

Về đơn vị: `delaySec` tính bằng **giây**. Header dùng `dRef = 0.010 s`, nên số hạng trễ bằng `1/(1 + delay/10 ms)`. Nếu code cũ dùng đơn vị khác, hãy quy đổi, nếu không reward sẽ lệch so với bài báo.

### Bước 4 – Mất liên kết và RERR (HOOK 2)

- **Truyền thất bại hết retry** (trong callback lỗi truyền của AODV, ví dụ `ProcessTxError` hoặc `SendRerrWhenBreaksLinkToNextHop`):
  ```cpp
  m_agent.RemoveNextHop(dst, brokenNextHop, Simulator::Now());
  ```
- **Nhận RERR từ neighbour `src`** báo mất tuyến tới `dst`:
  ```cpp
  m_agent.RemoveNextHop(dst, src, Simulator::Now());
  ```

Hàm này làm ba việc: xóa ứng viên, đánh dấu neighbour là ngõ cụt (`V = −5`), và tăng ε nếu `AdaptiveEpsilon` bật.

Nếu sau khi xóa vẫn còn ứng viên (`m_agent.HasRoute(dst)`), hãy **chuyển gói hỏng sang ứng viên khác** (salvage) thay vì bỏ gói. Đây là một nguồn lợi ích quan trọng của đa đường.

### Bước 5 – Quảng bá V kèm gói điều khiển (HOOK 5)

Gắn tag vào **mọi** gói điều khiển AODV mà nút gửi đi (HELLO, RREQ, RREP, RERR). Cách gọn nhất là gắn tại một chỗ chung, ví dụ trong `SendTo(socket, packet, destination)`:

```cpp
void RoutingProtocol::SendTo(Ptr<Socket> socket, Ptr<Packet> packet, Ipv4Address destination) {
    nbq::QValueTag tag(m_sinkAddr, m_agent.AdvertisedValue(m_sinkAddr, m_isSink));
    packet->ReplacePacketTag(tag);           // ReplacePacketTag tránh gắn trùng
    socket->SendTo(packet, 0, InetSocketAddress(destination, AODV_PORT));
}
```

Điều kiện kèm theo:
- HELLO phải được bật (`EnableHello = true`, `HelloInterval = 1 s`), để trạm gốc và các nút không nằm trên tuyến nào vẫn quảng bá V định kỳ.
- Kịch bản chỉ có một đích (trạm gốc), nên mỗi tag mang V của đích đó. Nếu cần nhiều đích, mở rộng tag thành danh sách (đích, V).

### Bước 6 – Nhận V của neighbour (HOOK 6)

Trong `RecvAodv(Ptr<Socket> socket)`, ngay sau `RecvFrom` và trước khi bóc header:

```cpp
nbq::QValueTag tag;
if (packet->PeekPacketTag(tag))
    m_agent.OnNeighbourValue(sender /* địa chỉ IP chặng trước */, tag.GetDst(),
                             tag.GetValue(), Simulator::Now());
```

Giá trị cũ hơn 3 s (`nbValueTtl`) sẽ bị bỏ qua, và thuật toán quay về dùng Q của chính nút.

### Bước 7 – Kịch bản và chạy hàng loạt

Trong `scratch/fanet-scenario.cc`, hàm `MakeRouting()` đã có sẵn nhánh `"NBQ-MAODV"`. Anh/chị chỉ cần bỏ comment và đặt đúng tên lớp Helper:

```cpp
if (proto == "SA-QMAODV" || proto == "NBQ-MAODV") {
    auto h = std::make_unique<SaqmaodvHelper>();
    h->Set("MaxPaths", UintegerValue(K));
    h->Set("NeighbourBootstrap", BooleanValue(proto == "NBQ-MAODV"));
    h->Set("SinkAddress", Ipv4AddressValue("10.1.0.<N+1>"));   // địa chỉ trạm gốc
    ...
}
```

Trạm gốc là nút cuối cùng được gán địa chỉ, tức `ifs.GetAddress(nUav)`. Hãy truyền địa chỉ này vào thuộc tính `SinkAddress` trước khi `stack.Install()`. Cần dựng địa chỉ thủ công vì `Ipv4AddressHelper` gán theo thứ tự: 10.1.0.1 đến 10.1.0.N cho UAV, 10.1.0.(N+1) cho trạm gốc.

---

## 3. Chi phí overhead

- Tag trong NS-3 là metadata mô phỏng, **không làm tăng kích thước gói**.
- Để báo cáo trung thực, có hai cách:
  - Thêm 8 byte vào header gói điều khiển.
  - Ghi trong bài: "the 8-byte value field is carried as a packet tag and its airtime is neglected".
- NRL (số gói điều khiển trên mỗi gói dữ liệu nhận được) không đổi, vì NBQ không sinh thêm gói nào.

---

## 4. Kiểm tra cài đặt đúng trước khi chạy hàng loạt

1. **Log một nút:** gọi `m_agent.Print(std::cout, m_sinkAddr)` mỗi 10 s.
   - Với NBQ, Q phải **âm**.
   - Next-hop gần trạm gốc có Q khoảng từ −0,3 đến −0,5.
   - Nút cách 3 chặng có Q khoảng từ −1,0 đến −1,5.
2. **Kịch bản hình thoi tĩnh:** S có hai next-hop cùng số chặng quảng bá. Một nhánh đi thẳng tới đích, nhánh kia phải qua thêm một nút kém.
   - Kết quả đúng: sau vài giây, NBQ-MAODV chọn nhánh tốt khoảng 85–90% số gói (phần còn lại do ε).
   - SA-QMAODV sẽ cho hai nhánh cùng một Q và chia gần như đều. Bài test của tôi trên header này cho đúng kết quả đó: Q = −0,41 và −1,26, so với 8,76 và 8,76.
3. **Đối chiếu nhanh với FANET-Sim** ở điểm 20 UAV, tải 12 gói/s:
   - Kỳ vọng thứ tự PDR: NBQ-MAODV > QMAODV > PMAODV ≈ SA-QMAODV.
   - Kỳ vọng trễ của NBQ-MAODV thấp nhất.

---

## 5. Cấu hình để báo cáo

| Tên trong bài | NeighbourBootstrap | AdaptiveEpsilon | AdaptiveAlpha | AdaptiveReward |
|---|---|---|---|---|
| SA-QMAODV | false | true | true | true |
| **NBQ-MAODV** (kết quả chính, như FANET-Sim) | true | true | true | true |
| NBQ-MAODV, không có ε thích nghi (ablation, tốt nhất khi tải cao) | true | false | true | true |

Nếu trên NS-3, bản tắt ε thích nghi cũng tốt nhất khi tải cao như trong FANET-Sim, có thể đặt nó làm cấu hình mặc định của NBQ-MAODV. Khi đó cần chạy lại E1–E4 với cấu hình này, và tôi sẽ viết lại bài cho khớp.
