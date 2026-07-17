"""
flat_rag.py — RAG "phẳng" làm đối chứng. (chủ: Hoàng)

Cố ý làm TỐI GIẢN như đa số hệ RAG thường:
  - chunk + embed + vector search top-k
  - nhồi thẳng vào LLM, hỏi gì trả nấy
  - KHÔNG có eligibility engine
  - KHÔNG lọc hiệu lực / hết hạn
  - KHÔNG biết chồng chéo

Vai trò: "đối thủ" để so sánh, cho thấy nó sai ở đâu và GrantPilot đúng ở đâu.
⚠️ Đừng tối ưu file này — nó cố ý đơn giản để phản ánh baseline thật.
"""

# TODO: hàm answer(question) -> str  (RAG tối giản)
