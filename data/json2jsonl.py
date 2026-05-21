import json

# 输入：标准 JSON 文件（数组格式）
with open("mechanism_invariant_supplemental_dataset_30_latex.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 输出：每行一个 JSON
with open("mechanism_invariant_supplemental_dataset_30_latex.jsonl", "w", encoding="utf-8") as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print("✅ JSON 转 JSONL 完成！")