# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path.cwd()
FRONTEND = ROOT / "desktop" / "frontend"
EXAMPLES = ROOT / "examples"
SKILLS = ROOT / "skills"
DOCS = ROOT / "docs"
MEMORY = ROOT / "memory"
EVALS = ROOT / "evals"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
SOURCE_ITEMS = [
    ROOT / "main.py",
    ROOT / "api",
    ROOT / "core",
    ROOT / "desktop",
    ROOT / "evals",
    ROOT / "llm",
    ROOT / "memory_providers",
    ROOT / "rag",
    ROOT / "search_providers",
    ROOT / "tools",
    ROOT / "weather_providers",
]

datas = [
    (str(FRONTEND), "frontend"),
    (str(EXAMPLES), "examples"),
    (str(SKILLS), "skills"),
    (str(DOCS), "docs"),
    (str(MEMORY), "memory"),
    (str(EVALS / "cases"), "evals/cases"),
    (str(ROOT / "rag" / "eval_cases.json"), "rag"),
    (str(README), "."),
    (str(CHANGELOG), "."),
]
datas.extend((str(item), f"source/{item.name}") for item in SOURCE_ITEMS if item.exists())

a = Analysis(
    [str(ROOT / "desktop" / "build" / "uta_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "webview.platforms.cocoa",
        "certifi",
        "desktop.api",
        "desktop.app",
        "desktop.events",
        "desktop.message_router",
        "desktop.runner",
        "desktop.settings_store",
        "desktop.skill_store",
        "evals.runner",
        "desktop.rag_client",
        "api",
        "api.server",
        "core.executor",
        "core.evidence",
        "core.loop",
        "core.planner",
        "core.reflection",
        "core.router",
        "core.skill_loader",
        "core.state",
        "core.task_parser",
        "core.verifier",
        "llm.llm_client",
        "memory_providers.json_memory_provider",
        "tools.authorization",
        "tools.code_tool",
        "tools.file_tool",
        "tools.geo_tool",
        "tools.history_tool",
        "tools.langchain_adapter",
        "tools.langchain_common_tools",
        "tools.mock_tool",
        "tools.report_tool",
        "tools.table_tool",
        "tools.text_tool",
        "rag",
        "rag.kb",
        "rag.defaults",
        "rag.models",
        "rag.errors",
        "rag.cli",
        "rag.api",
        "rag.benchmark",
        "rag.evaluation",
        "rag.seed",
        "rag.loaders.base",
        "rag.loaders.document_loaders",
        "rag.loaders.text_loader",
        "pypdf",
        "docx",
        "rag.chunkers.base",
        "rag.chunkers.fixed_chunker",
        "rag.embeddings.base",
        "rag.embeddings.hashing_embedder",
        "rag.generation.base",
        "rag.generation.echo_generator",
        "rag.store.base",
        "rag.store.sqlite_store",
        "rag.retrieval.base",
        "rag.retrieval.hybrid_retriever",
        "rag.retrieval.reranker",
        "rag.retrieval.vector_retriever",
        "search_providers",
        "search_providers.base_search_provider",
        "search_providers.bing_search_provider",
        "search_providers.duckduckgo_search_provider",
        "search_providers.factory",
        "search_providers.fixture_search_provider",
        "search_providers.http_search_provider",
        "weather_providers",
        "weather_providers.base_weather_provider",
        "weather_providers.factory",
        "weather_providers.open_meteo_weather_provider",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # RAG 真实模型路径的 ML 重库。
        # 打包环境 sys.frozen=True 时 rag_client 强制 use_real=False，
        # 走 HashingEmbedder（纯标准库），这些库运行时永不加载。
        # 仅因 local_embedder.py 方法体内的 import 被 PyInstaller 静态拖入。
        "torch",
        "transformers",
        "sentence_transformers",
        "scipy",
        "sklearn",
        "scikit_learn",
        # 上述库的传递依赖，一并清理
        "networkx",
        "joblib",
        "threadpoolctl",
        "sympy",
        "mpmath",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UTA Desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UTA Desktop",
)

app = BUNDLE(
    coll,
    name="UTA Desktop.app",
    icon=None,
    bundle_identifier="com.uta.desktop",
    info_plist={
        "CFBundleName": "UTA Desktop",
        "CFBundleDisplayName": "UTA Desktop",
        "CFBundleShortVersionString": "1.10.0",
        "CFBundleVersion": "1.10.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)
