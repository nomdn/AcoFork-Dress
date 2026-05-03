import os
from pathlib import Path as p_pathlib
import subprocess
import random
import json
from typing import Annotated
import httpx
import colorama
from colorama import Fore, Style
import uvicorn
import logging
from dotenv import load_dotenv
from git import Repo
import asyncio
import json
from fastapi import (
    FastAPI,
    Response,
    Request,
    BackgroundTasks,
    HTTPException,
    Header,
    Query,
    Path,
    status
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import urljoin, urlparse
from httpx import TimeoutException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager  # 添加这个导入
from dress_tools import run_git_pull, get_github_index,random_pick,random_pick_group
from tools_v2 import build_index_by_group, convert_index_group_to_index_id



index_group = {}
index_id = {}
ports = 8092
log_level = "INFO"
lite_mode = "false"
force_remote_index = "false"
# 统一加载逻辑
load_dotenv()  # 先加载 .env


ports = int(os.environ.get("PORTS") or ports)
log_level = os.environ.get("LOG_LEVEL") or log_level
lite_mode = os.environ.get("FORCE_LITE") or lite_mode
force_remote_index = os.environ.get("FORCE_REMOTE") or force_remote_index

# 安全地设置日志级别，处理None值和无效值
if log_level is None:
    log_level = "INFO"
try:
    log_level_value = getattr(logging, log_level.upper(), logging.INFO)
except AttributeError:
    log_level_value = logging.INFO

logging.basicConfig(
    level=log_level_value,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
)

# 确保 uvicorn 的日志级别与应用一致
logging.getLogger("uvicorn.access").setLevel(log_level_value)
logging.getLogger("uvicorn.error").setLevel(log_level_value)

# 挂载整个目录，支持 index.html 自动路由
BASE_DIR = p_pathlib(__file__).resolve().parent
# 支持的图片扩展名（可按需增减）
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


if not os.path.exists("Acofork-Categorized") and lite_mode != "true":
    logging.info("未在当前目录发现Acofork-Categorized仓库，将以轻量API运行")
    lite_mode = "true"
    try:
        index_id = asyncio.run(get_github_index())
        index_group = asyncio.run(get_github_index("index_1.json"))
    except Exception as e:
        logging.error(f"获取远端数据失败：{e}")
        raise RuntimeError("无法连接到远程服务器获取数据")
elif lite_mode == "true":
    # 即使存在 Dress 目录，如果用户强制设置为轻量模式，也要使用远程数据
    logging.info("强制使用轻量 API 运行模式")
    try:
        index_id = asyncio.run(get_github_index())
        index_group = asyncio.run(get_github_index())
    except Exception as e:
        logging.error(f"获取远端数据失败：{e}")
        raise RuntimeError("无法连接到远程服务器获取数据")
else:
    # 在非轻量模式下，也需要初始化data变量，以防万一需要使用
    data = None




app = FastAPI(
    title="AcoFork",
    description="关注b站二叉树树谢谢喵",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"])
@app.middleware("http")
async def spa_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # 如果响应是 404，并且请求路径不是 API 或静态资源，则返回 index.html
    if (
        response.status_code == 404 
        and not request.url.path.startswith("/v1/") # 你的 API 前缀
        and not request.url.path.startswith("/img/") # 你的图片资源
        and not request.url.path.startswith("/static/") # 如果你有其他静态资源
        and not os.path.splitext(request.url.path)[1] # 不是请求一个带扩展名的文件 (如 .js, .css)
    ):
        # 返回 Vue 应用的入口文件
        return FileResponse(os.path.join(BASE_DIR, "public", "index.html"))
    
    return response

"""


async def run_one_sync():
    global index_group, index_id, jsdelivr_ok, github_ok
    async with httpx.AsyncClient() as client:
        # Check GitHub
        try:
            resp = await client.get("https://github.com", timeout=10.0)
            github_ok = resp.status_code == 200
        except httpx.RequestError:
            github_ok = False

        # Check jsDelivr
        jsdelivr_ok = False
        jsdelivr_urls = [
            "https://cdn.jsdelivr.net/",
            "https://fastly.jsdelivr.net/",
            "https://gcore.jsdelivr.net/",
            "https://testingcf.jsdelivr.net/",
        ]
        for url in jsdelivr_urls:
            try:
                resp = await client.get(url, timeout=10.0)
                if resp.status_code in (200, 301):
                    jsdelivr_ok = True
                    break
            except httpx.RequestError:
                continue  # Try next URL
    # 使用无限循环替代单次sleep

    if lite_mode != "true":
        logging.info("开始执行本地Dress仓库同步...")
        await asyncio.to_thread(run_git_pull)  # run_git_pull 不是异步函数
        if force_remote_index == "true":
            index_id = await get_github_index("index_0.json")
            index_group = await get_github_index("index_1.json")
            with open("public/index_0.json", "w", encoding="utf-8") as f:
                json.dump(index_id, f, ensure_ascii=False, indent=4)
            with open("public/index_1.json", "w", encoding="utf-8") as f:
                json.dump(index_group, f, ensure_ascii=False, indent=4)
        else:
            try:
                repo = Repo("Dress")
                index = build_index_by_group(repo)
                index_group = index

                index_id = convert_index_group_to_index_id(index)
                with open("public/index_1.json", "w", encoding="utf-8") as f:
                    json.dump(index_group, f, ensure_ascii=False, indent=4)
                with open("public/index_0.json", "w", encoding="utf-8") as f:
                    json.dump(index_id, f, ensure_ascii=False, indent=4)
                logging.debug("本地 Dress 仓库同步完成")
            except FileNotFoundError as e:
                logging.error(f"Dress目录不存在: {e}")
            except PermissionError as e:
                logging.error(f"权限不足: {e}")
            except Exception as e:
                logging.error(f"自动同步时构建索引失败: {e}")
    else:
        logging.debug("开始执行远程数据同步...")
        try:
            index_id = await get_github_index(index="index_0.json")
            index_group = await get_github_index(index="index_1.json")
            with open("public/index_0.json", "w", encoding="utf-8") as f:
                json.dump(index_id, f, ensure_ascii=False, indent=4)
            with open("public/index_1.json", "w", encoding="utf-8") as f:
                json.dump(index_group, f, ensure_ascii=False, indent=4)
            logging.debug(f"已从 GitHub 获取最新数据，共{len(index_id)}项数据)")
        except Exception as e:
            logging.error(f"远程数据同步失败：{e}")  # 每 10 秒同步一次，便于观察
"""

@app.get("/v1/acofork", summary="获取 acofrok 的自拍")
@app.post("/v1/acofork", summary="获取 acofrok 的自拍")
async def random_setu(request: Request,
                      num: int = Query(1, description="可选，指定返回数量，默认为 1"),
                      group: str = Query(None, description="可选，指定分组名称以获取该分组的图片"),):
    """
    你 GET 一下就行了
    参数放 url
    POST 也行，参数放在 body 里，json 格式，num 和 group 都是可选的，例如：
    {"num": 3, "group": "nekozzx"}
    """
    # 检查是否为 POST 请求，如果是，则从请求体获取参数
    if request.method == "POST":
        try:
            body = await request.json()
            num = body.get("num", num)
            group = body.get("group", group)
            if isinstance(group, str):
                group = [group]  # 如果是单个字符串，转换为列表
        except Exception:
            pass
    elif request.method == "GET":
        if group:
            group = group.split("|")
        else:
            pass
    else:
        raise HTTPException(status_code=405, detail="Method Not Allowed")

    base_url = request.base_url
    global index_id,index_group

    max_count = len(index_id.keys())
    if max_count == 0:
        # 立即尝试读本地索引
        try:
            with open("public/index_0.json", "r", encoding="utf-8") as f:
                index_id = json.load(f)
                max_count = len(index_id.keys())
            with open("public/index_1.json", "r", encoding="utf-8") as f:
                index_group = json.load(f)
        except:
            return {"code": 500, "message": "No data available yet, please try again later."}
    
    # 确保 num 不超过最大值
    num = min(num, max_count)
    group_all_count = 0 
    results = []
    used_paths = set()  # 用于存储已使用的 path，确保不重复
    if lite_mode == "true":
        img_base_url = "https://testingcf.jsdelivr.net/gh/Cute-Dress/Dress@master/"
    else:
        img_base_url = f"{base_url}img/"
    if group:
        
        for one_group in group:
            if one_group in index_group:
                group_all_count += len(index_group[one_group]["contribution"])
            else:
                raise HTTPException(status_code=404, detail=f"Group {one_group} Not Found")
        num = min(num, group_all_count)
        while len(results) < num:
            now_group = random.choice(group)
            entry = await random_pick_group(index_group, img_base_url, now_group)
            if entry["url"] not in used_paths:
                used_paths.add(entry["url"])
                results.append(entry)
            else:
                continue
    else:
        # 随机选择 num 个不同的图片
        while len(results) < num:
            entry = await random_pick(index_id, img_base_url)
            if entry["url"] not in used_paths:
                used_paths.add(entry["url"])
                results.append(entry)
            else:
                continue
    # 如果只请求一个，返回单个对象，保持向后兼容
    if num == 1 and results:
        return results[0]
    return results





# 克隆仓库


@app.get("/v1/health", summary="健康检查")
async def health_check():

    return {
        "status": "ok",
        "lite_mode": lite_mode,
    }


@app.get("/v1/acofork/index/{name}", summary="获取指定索引文件内容")
@app.post("/v1/acofork/index/{name}", summary="获取指定索引文件内容")
async def return_index(
    name: Annotated[
        str, Path(description="索引名称，支持 index_0.json 和 index_1.json")
    ],
):
    """
    获取指定索引文件内容
    """
    if name not in ["index_0.json", "index_1.json"]:
        raise HTTPException(status_code=400, detail="Invalid index name")
    try:
        with open(f"public/{name}", "r", encoding="utf-8") as f:
            index_data = json.load(f)
        return index_data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Index file not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Index file is corrupted")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading index file: {e}")


@app.get("/v1/acofork/group/{group}", summary="获取指定分组的图片信息")
@app.post("/v1/acofork/group/{group}", summary="获取指定分组的图片信息")
async def return_group_info(group: Annotated[str, Path(description="分组名称")]):
    """
    获取指定分组名称的图片信息
    """
    try:
        global index_group
        if len(index_group) == 0:  # 索引为空时立即尝试读本地索引
            try:
                with open("public/index_1.json", "r", encoding="utf-8") as f:
                    index_group = json.load(f)
            except Exception as e:
                logging.warning(f"本地作者索引文件读取失败：{e}")
                # 立即开始一次同步
                raise HTTPException(status_code=503, detail="Index is not available yet, please try again later.")

        group_data = index_group[group]
        return {group: group_data}
    except KeyError:
        raise HTTPException(status_code=404, detail="Group not found")

@app.get("/i/love/you",include_in_schema=False)
async def love_you(response: Response):
    which = random.randint(0, 1)
    if which == 0:
        response.status_code = 520
        return {
        "zh_CN": "我喜欢二叉树树",
        "zh_TW": "我喜歡二叉树树",
        "ar_SA": "أنا أحب Acofork",
        "en_US": "I love Acofork",
        "en_GB": "I love Acofork",
        "fr_FR": "J'aime Acofork",
        "ru_RU": "Я люблю Acofork",
        "es_ES": "Me encanta Acofork",
        "de_DE": "Ich liebe Acofork",
        "it_IT": "Amo Acofork",
        "pt_PT": "Eu amo Acofork",
        "pt_BR": "Eu amo Acofork",
        "ja_JP": "私はAcoforkが大好きです",
        "ko_KR": "나는 Acofork를 사랑한다",
        "hi_IN": "मैं Acofork से प्यार करता हूँ",
        "bn_BD": "আমি Acofork ভালোবাসি",
        "ur_PK": "میں Acofork سے محبت کرتا ہوں",
        "fa_IR": "من Acofork را دوست دارم",
        "pa_IN": "ਮੈਨੂੰ Acofork ਨਾਲ ਪਿਆਰ ਹੈ",
        "ta_IN": "நான் Acofork ஐ விரும்புகிறேன்",
        "te_IN": "నేను Acofork ను ప్రేమిస్తున్నాను",
        "mr_IN": "मला Acofork आवडते",
        "gu_IN": "હું Acofork પ્રેમ કરું છું",
        "kn_IN": "ನಾನು Acofork ಅನ್ನು ಪ್ರೀತಿಸುತ್ತೇನೆ",
        "ml_IN": "ഞാൻ Acofork നെ സ്നേഹിക്കുന്നു",
        "or_IN": "ମୁଁ Acofork କୁ ଭଲପାଏ",
        "as_IN": "মই Acofork ভাল পাওঁ",
        "ks_IN": "بہٕ Acofork چھِ محبت کران",
        "sd_IN": "مان Acofork سان پيار ڪندو آهيان",
        "sa_IN": "अहं Acofork प्रेमयामि",
        "ne_NP": "म Acofork लाई माया गर्छु",
        "si_LK": "මම Acofork වලට ආදරෙයි",
        "my_MM": "ကျွန်တော် Acofork ကို ချစ်တယ်",
        "km_KH": "ខ្ញុំស្រលាញ់ Acofork",
        "lo_LA": "ຂ້ອຍຮັກ Acofork",
        "vi_VN": "Tôi yêu Acofork",
        "th_TH": "ฉันรัก Acofork",
        "id_ID": "Saya mencintai Acofork",
        "ms_MY": "Saya sayang Acofork",
        "tl_PH": "Mahal ko ang Acofork",
        "sw_KE": "Nampenda Acofork",
        "ha_NG": "Ina son Acofork",
        "yo_NG": "Mo nifẹ Acofork",
        "ig_NG": "Ahụrụ m Acofork n'anya",
        "zu_ZA": "Ngiyamthanda u-Acofork",
        "af_ZA": "Ek is lief vir Acofork",
        "so_SO": "Waan jeclahay Acofork",
        "am_ET": "እኔ Acofork እወዳለሁ",
        "ti_ER": "ኣነ ን Acofork የፍቅር እየ",
        "om_ET": "Ani Acofork nan jaalladha",
        "rw_RW": "Nkunda Acofork",
        "rn_BI": "Ndarakunda Acofork",
        "mt_MT": "Inħobb Acofork",
        "is_IS": "Ég elska Acofork",
        "ga_IE": "Is breá liom Acofork",
        "gd_GB": "Tha gaol agam air Acofork",
        "cy_GB": "Rwyf wrth fy modd â Acofork",
        "br_FR": "Karet a ran Acofork",
        "eu_ES": "Acofork maite dut",
        "ca_ES": "M'estimo Acofork",
        "gl_ES": "Quero a Acofork",
        "sq_AL": "Unë e dua Acofork",
        "bs_BA": "Volim Acofork",
        "hr_HR": "Volim Acofork",
        "sr_RS": "Волим Acofork",
        "cnr_ME": "Volim Acofork",
        "mk_MK": "Го сакам Acofork",
        "bg_BG": "Обичам Acofork",
        "ro_RO": "Îl iubesc pe Acofork",
        "ro_MD": "Îl iubesc pe Acofork",
        "hu_HU": "Szeretem Acofork-ot",
        "sk_SK": "Milujem Acofork",
        "cs_CZ": "Miluji Acofork",
        "pl_PL": "Kocham Acofork",
        "sl_SI": "Ljubim Acofork",
        "lv_LV": "Es mīlu Acofork",
        "lt_LT": "Aš myliu Acofork",
        "et_EE": "Ma armastan Acoforki",
        "fi_FI": "Rakastan Acoforkia",
        "sv_SE": "Jag älskar Acofork",
        "da_DK": "Jeg elsker Acofork",
        "no_NO": "Jeg elsker Acofork",
        "ka_GE": "მე მიყვარს Acofork",
        "hy_AM": "Ես սիրում եմ Acofork",
        "az_AZ": "Mən Acofork-u sevirəm",
        "kk_KZ": "Мен Acofork жақсы көремін",
        "ky_KG": "Мен Acofork жакшы көрөм",
        "tg_TJ": "Ман Acofork-ро дӯст медорам",
        "tk_TM": "Men Acofork-i söýýärin",
        "uz_UZ": "Men Acofork-ni yaxshi ko'raman",
        "mn_MN": "Би Acofork-д хайртай",
        "ps_AF": "زه Acofork سره مینه لرم",
        "sd_AF": "زه Acofork سان پیار کوم",
        "mg_MG": "Tiako i Acofork",
        "ny_MW": "Ndimakonda Acofork",
        "st_ZA": "Ke rata Acofork",
        "tn_ZA": "Ke rata Acofork",
        "ts_ZA": "Ndzi rhandza Acofork",
        "ve_ZA": "Ndi funa Acofork",
        "nr_ZA": "Ngiyamuthanda Acofork",
        "ss_ZA": "Ngiyamtsandza Acofork"
        }
    else:
        response.status_code = status.HTTP_418_IM_A_TEAPOT
        return {
            "zh_CN": "我是一个茶壶！！！！！",
            "zh_TW": "我是一個茶壺！！！！！",
            "ja_JP": "私はティーポットです！！！！！",
            "en_US": "I am a teapot!!!!!",
            "en_GB": "I am a teapot!!!!!",
            "fr_FR": "Je suis une théière !!!!!",
            "de_DE": "Ich bin eine Teekanne !!!!!",
            "es_ES": "¡Soy una tetera !!!!!",
            "it_IT": "Sono una teiera !!!!!",
            "pt_BR": "Eu sou um bule !!!!!",
            "ru_RU": "Я чайник !!!!!",
            "ko_KR": "저는 주전자입니다 !!!!!",
            "ar_SA": "أنا إبريق شاي !!!!!",
            "th_TH": "ฉันเป็นกาชงชา !!!!!",
            "vi_VN": "Tôi là một cái ấm trà !!!!!",
            "id_ID": "Saya adalah teko !!!!!",
            "hi_IN": "मैं एक चायदान हूँ !!!!!",
            "tr_TR": "Ben bir demliğim !!!!!",
            "nl_NL": "Ik ben een theepot !!!!!",
            "pl_PL": "Jestem czajnikiem !!!!!",
            "sv_SE": "Jag är en tekanna !!!!!",
        }


if lite_mode != "true":
    app.mount("/img", StaticFiles(directory=BASE_DIR / "Acofork-Categorized"), name="static")
app.mount("/", StaticFiles(directory=BASE_DIR / "public", html=True), name="static")

if __name__ == "__main__":
    colorama.init(autoreset=True)
    print(f"🚀 启动服务: http://0.0.0.0:{ports}")

    # 创建事件循环并同时运行自动同步和web服务器

    # 启动web服务器
    uvicorn.run(app, host="0.0.0.0", port=ports, log_level=log_level.lower())
