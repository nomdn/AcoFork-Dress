import json
import os
import subprocess
import logging
import httpx
from os import name
from pathlib import Path
import asyncio
from git import Repo
from typing import List



from pathlib import Path
import os, time
from git import Repo
from typing import List, Tuple

# 禁用httpx的DEBUG日志，避免网络请求产生过多调试信息
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
                    )
def get_all_file_path(path: str) -> Tuple[List[str], List[str]]:
    """
    获取目录下的所有图片和 README 文件路径

    Returns:
        Tuple[List[str], List[str]]: (图片相对路径列表，README 相对路径列表)
        路径格式：相对于 path 目录的 POSIX 风格字符串
    """
    p = Path(path).resolve()
    img_paths = []
    readme_paths = []

    # 统一用小写匹配（兼容 Windows/Linux）
    IMG_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    README_NAMES = {"readme", "readme.md", "readme.txt", "readme.rst"}

    for files in p.rglob("*"):
        try:
            if not files.is_file():
                continue

            # 计算相对路径（关键！）
            relative_path = files.relative_to(p)
            # 转换为 POSIX 风格（/ 分隔符）
            posix_path = relative_path.as_posix()

            # 小写后缀匹配
            suffix_lower = files.suffix.lower()
            name_lower = files.name.lower()

            if suffix_lower in IMG_EXTENSIONS:
                img_paths.append(posix_path)

            if name_lower in README_NAMES:
                readme_paths.append(posix_path)

        except Exception as e:
            logging.warning(f"处理文件 {files} 时出错：{e}")
            continue
    img_paths.sort()
    readme_paths.sort()

    logging.info(f"扫描完成：{len(img_paths)} 张图片，{len(readme_paths)} 个 README")
    return img_paths, readme_paths




async def build_index_by_group(repo: str):
    index_group = {}
    img_paths, _ = get_all_file_path(repo)
    
    DEFAULT_AUTHOR = {
        "avatar_url": "https://avatars.githubusercontent.com/u/180811437?v=4",
        "github_username": "afoim"
    }
    VALID_EXTS = {"jpg","jpeg","png","gif","bmp","webp"}
    
    for img_path in img_paths:
        parts = Path(img_path).parts
        tags = parts[1:-1]
        logging.debug(f"处理{img_path}")
        if parts[0] not in index_group:
            index_group[parts[0]] = {
                "avatar_url": DEFAULT_AUTHOR["avatar_url"],
                "github_username": DEFAULT_AUTHOR["github_username"],
                "contribution": []
            }
        
        index_group[parts[0]]["contribution"].append({
                "path": img_path,
                "tags": tags,
            })

            

    return index_group
async def convert_index_group_to_index_id(index_group: dict) -> dict:
    index_id ={}
    id = 1 
    for authors in index_group.keys():
        for contribution in index_group[authors]["contribution"]:
            logging.debug(f"处理{contribution},ID 为{id}")
            contribution["group"]=authors
            index_id[id] = contribution
            id += 1
    return index_id
async def convert_index_group_to_index_tag(index_group: dict) -> dict:
    index_tag = {}
    for group,data in index_group.items():
        for contribution in data["contribution"]:
            for tag in contribution["tags"]:
                if tag not in index_tag:
                    index_tag[tag] = []
                contribution["group"]=group
                index_tag[tag].append(contribution)
    return index_tag
            




if __name__ == "__main__":
    index_group=asyncio.run(build_index_by_group("Acofork-Categorized"))
    with open("public/index_1.json", "w", encoding="utf-8") as f:
        json.dump(index_group, f, ensure_ascii=False, indent=4)
    index_id = asyncio.run(convert_index_group_to_index_id(index_group))
    with open("public/index_0.json", "w", encoding="utf-8") as f:
        json.dump(index_id, f, ensure_ascii=False, indent=4)
    index_tag = asyncio.run(convert_index_group_to_index_tag(index_group))
    with open("public/index_2.json", "w", encoding="utf-8") as f:
        json.dump(index_tag, f, ensure_ascii=False, indent=4)