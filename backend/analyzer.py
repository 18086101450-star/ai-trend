import logging
import re
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional


logger = logging.getLogger(__name__)

STOPWORDS = set(
    "the a an is are was were be been being have has had do does did will would "
    "can could should may might shall must need ought dare used to upon than that "
    "this these those it its they them their what which who whom whose why how "
    "when where all each every both few many some any no not only but or and "
    "if because so as for until while of in on at by with from into through "
    "during before after above below between out off over under again further "
    "then once here there about against around down up etc i e g vs "
    "versus via per among unto de la le les un une des du au aux ce cet cette "
    "ces son sa ses notre nos votre vos leur leurs nouveau nouvelles "
    "based on using method approach model results show propose introduce present "
    "first second third also well however therefore thus moreover "
    "furthermore additionally consequently particularly specifically especially "
    "namely importantly effectively efficiently significantly substantially "
    "dramatically rapidly increasingly widely commonly typically often "
    "generally frequently usually recently currently previously traditionally "
    "large small high low long short wide deep broad strong weak fast slow "
    "hard soft easy difficult simple complex efficient effective robust scalable "
    "accurate precise reliable stable consistent flexible adaptive dynamic "
    "various multiple diverse extensive comprehensive thorough complete partial "
    "total full overall global local general specific particular individual "
    "unique distinct separate independent automatic manual direct indirect "
    "primary secondary tertiary quantitative qualitative comparative experimental "
    "theoretical empirical practical real state cutting best our we their its".split()
)

TECH_BIGRAMS = {
    "machine learning", "deep learning", "reinforcement learning", "transfer learning",
    "federated learning", "meta learning", "few-shot learning", "zero-shot learning",
    "self-supervised learning", "unsupervised learning", "supervised learning",
    "semi-supervised learning", "continual learning", "lifelong learning",
    "active learning", "multi-modal", "multimodal", "large language",
    "language model", "foundation model", "diffusion model", "generative model",
    "graph neural", "neural network", "transformer model", "attention mechanism",
    "computer vision", "natural language", "information retrieval",
    "knowledge graph", "recommender system", "decision making",
    "reinforcement learning from human feedback", "retrieval-augmented generation",
    "chain of thought", "in-context learning", "instruction tuning",
    "parameter efficient", "quantization", "knowledge distillation",
    "mixture of experts", "sparse attention", "linear attention",
    "position encoding", "tokenization", "embedding model",
    "contrastive learning", "representation learning", "world model",
    "autonomous agent", "tool use", "code generation",
}

AI_EXPLANATIONS = {
    "transformer": {
        "explanation": "A neural network architecture based on self-attention mechanism that processes entire sequences in parallel rather than sequentially.",
        "meaning": "The fundamental architecture behind most modern AI breakthroughs, enabling efficient parallel processing of long-range dependencies in data.",
        "application": "Used in LLMs (GPT, BERT), machine translation, text generation, image processing, and multimodal AI systems.",
    },
    "attention": {
        "explanation": "A mechanism that allows models to focus on relevant parts of input data by learning weighted importance scores across positions.",
        "meaning": "Enables models to capture long-range dependencies and contextual relationships, forming the core of transformer architectures.",
        "application": "Machine translation, text summarization, image captioning, speech recognition, and document understanding.",
    },
    "diffusion": {
        "explanation": "A generative AI method that learns to reverse a gradual noising process to create high-quality data from random noise.",
        "meaning": "Revolutionized image generation by producing higher quality and more diverse outputs than previous GAN-based approaches.",
        "application": "Image generation (DALL-E, Stable Diffusion, Midjourney), video generation, 3D content creation, drug discovery.",
    },
    "large language model": {
        "explanation": "A deep neural network trained on massive text corpora to understand and generate human-like text through next-token prediction.",
        "meaning": "Represents a paradigm shift in AI, demonstrating emergent abilities like reasoning, coding, and tool use at scale.",
        "application": "Chatbots, code generation, content creation, question answering, translation, summarization, and AI assistants.",
    },
    "reinforcement learning from human feedback": {
        "explanation": "A training technique that fine-tunes language models using human preferences as a reward signal to align outputs with human values.",
        "meaning": "Critical for making AI systems safe, helpful, and aligned with human intent, used extensively in production LLMs.",
        "application": "AI alignment, content moderation, reducing harmful outputs, improving helpfulness in chatbots, personalized recommendations.",
    },
    "retrieval-augmented generation": {
        "explanation": "A hybrid approach that combines information retrieval with text generation, allowing models to access external knowledge during inference.",
        "meaning": "Addresses knowledge cutoff, hallucination, and factual accuracy issues in LLMs by grounding outputs in retrieved documents.",
        "application": "Enterprise chatbots, knowledge-intensive Q&A, legal document analysis, medical diagnosis support, research assistance.",
    },
    "chain of thought": {
        "explanation": "A prompting technique that guides LLMs to produce intermediate reasoning steps before arriving at a final answer.",
        "meaning": "Significantly improves reasoning capabilities in LLMs, enabling complex multi-step problem solving previously thought impossible.",
        "application": "Mathematical reasoning, logical deduction, code debugging, scientific reasoning, planning and decision making.",
    },
    "mixture of experts": {
        "explanation": "An architecture that uses multiple specialized sub-networks (experts) with a gating mechanism to activate only relevant experts per input.",
        "meaning": "Enables scaling models to trillions of parameters while keeping inference costs manageable by only using a subset of parameters.",
        "application": "Large-scale language models, efficient training and inference, multimodal models, sparse computation.",
    },
    "quantization": {
        "explanation": "A technique that reduces the precision of model weights and activations (e.g., from 32-bit to 4-bit) to decrease memory and compute requirements.",
        "meaning": "Makes large models deployable on consumer hardware and edge devices, democratizing access to advanced AI capabilities.",
        "application": "Mobile AI deployment, edge computing, on-device inference, reducing cloud serving costs, enabling local LLMs.",
    },
    "multimodal": {
        "explanation": "AI systems capable of processing and integrating multiple types of data (text, images, audio, video) simultaneously.",
        "meaning": "Brings AI closer to human-like perception by understanding the world through multiple senses and data modalities.",
        "application": "Image captioning, video understanding, document AI, robotics perception, accessibility tools, content moderation.",
    },
    "agent": {
        "explanation": "An autonomous AI system that can perceive its environment, make decisions, and take actions to achieve specified goals.",
        "meaning": "Represents the evolution from passive AI models to active systems capable of independent task completion and tool use.",
        "application": "Automated code development, web browsing, customer service, robotics control, data analysis pipelines, workflow automation.",
    },
    "knowledge distillation": {
        "explanation": "A technique where a smaller student model is trained to mimic the behavior of a larger teacher model, compressing knowledge.",
        "meaning": "Enables deployment of near-state-of-the-art performance on resource-constrained devices by transferring knowledge from large models.",
        "application": "Model compression, mobile AI, real-time inference, edge deployment, reducing computational costs while maintaining accuracy.",
    },
    "embedding": {
        "explanation": "A dense vector representation of data (text, images, etc.) that captures semantic meaning in a continuous vector space.",
        "meaning": "The foundation of modern representation learning, enabling semantic search, clustering, and similarity comparisons across AI systems.",
        "application": "Semantic search, recommendation systems, clustering, anomaly detection, document retrieval, face recognition.",
    },
    "federated learning": {
        "explanation": "A machine learning approach where models are trained across decentralized devices without raw data leaving the local device.",
        "meaning": "Addresses privacy concerns by keeping sensitive data on-device while still enabling collaborative model improvement.",
        "application": "Healthcare AI, mobile keyboard prediction, personalized recommendations, financial services, privacy-preserving analytics.",
    },
    "few-shot learning": {
        "explanation": "The ability of a model to learn and generalize from only a small number of training examples per class.",
        "meaning": "Reduces the need for large labeled datasets, making AI more practical for niche domains with limited data availability.",
        "application": "Medical imaging with rare diseases, personalized AI, niche domain adaptation, rapid prototyping, low-resource languages.",
    },
    "parameter-efficient fine-tuning": {
        "explanation": "Techniques (LoRA, adapters, prefix tuning) that adapt large pre-trained models by training only a small set of additional parameters.",
        "meaning": "Democratizes fine-tuning of large models by reducing memory and compute requirements from thousands to single GPU hours.",
        "application": "Customizing LLMs for specific tasks, domain adaptation, personalization, multi-task learning with shared backbones.",
    },
    "world model": {
        "explanation": "An internal representation that an AI system learns about how its environment works, enabling prediction and planning.",
        "meaning": "Crucial step towards general intelligence by giving AI systems the ability to simulate outcomes and plan actions in complex environments.",
        "application": "Autonomous driving simulation, robotics planning, game AI, model-based reinforcement learning, video prediction.",
    },
    "sparse attention": {
        "explanation": "A optimization technique that reduces the quadratic complexity of standard attention by attending to only a subset of positions.",
        "meaning": "Enables transformers to process much longer sequences (100K+ tokens) efficiently, unlocking new applications.",
        "application": "Long document processing, code repository understanding, genomics sequence analysis, long video understanding.",
    },
    "knowledge graph": {
        "explanation": "A structured representation of entities and their relationships, forming a network of interconnected real-world concepts.",
        "meaning": "Bridges symbolic AI with neural approaches, enabling reasoning, explainability, and structured knowledge integration.",
        "application": "Search engines, recommendation systems, drug discovery, question answering, enterprise data integration, fraud detection.",
    },
    "contrastive learning": {
        "explanation": "A self-supervised learning method that learns representations by pulling similar pairs together and pushing dissimilar pairs apart.",
        "meaning": "Enables learning powerful representations without labeled data, achieving near-supervised performance on many tasks.",
        "application": "Vision representation learning, text embedding, multimodal alignment (CLIP), speaker recognition, anomaly detection.",
    },
    "autoregressive": {
        "explanation": "A model that generates outputs sequentially, predicting each next token conditioned on all previous tokens.",
        "meaning": "The dominant paradigm for text generation in LLMs (GPT family), enabling coherent long-form content generation.",
        "application": "Text generation, code completion, time series forecasting, music generation, speech synthesis.",
    },
    "language model": {
        "explanation": "A probability distribution over sequences of words trained on large text corpora to predict and generate human language.",
        "meaning": "The core technology behind conversational AI, code generation, and knowledge systems - the 'brain' of modern AI applications.",
        "application": "ChatGPT-like assistants, code completion (GitHub Copilot), translation, summarization, search engines, and creative writing tools.",
    },
    "foundation model": {
        "explanation": "A large-scale AI model trained on broad data that can be adapted to a wide range of downstream tasks via fine-tuning or prompting.",
        "meaning": "Represents a paradigm shift from task-specific models to general-purpose AI systems that serve as reusable building blocks.",
        "application": "GPT-4, Claude, Llama for text; DALL-E, Stable Diffusion for images; Codex for code - adaptable to thousands of specific tasks.",
    },
    "reinforcement learning": {
        "explanation": "A machine learning paradigm where an agent learns to make decisions by interacting with an environment and receiving rewards or penalties.",
        "meaning": "Key to achieving superhuman performance in games, robotics control, and scenarios requiring sequential decision-making under uncertainty.",
        "application": "Game AI (AlphaGo, Dota 2), robotics control, autonomous driving, recommendation systems, resource optimization, and LLM alignment (RLHF).",
    },
    "representation learning": {
        "explanation": "A set of techniques that allow machines to automatically discover the optimal way to represent data for a given task.",
        "meaning": "Eliminates the need for manual feature engineering, enabling AI to learn from raw data and discover hidden patterns automatically.",
        "application": "Self-supervised learning (BERT, GPT), word embeddings, graph embeddings, speaker recognition, medical image analysis, recommender systems.",
    },
    "deep learning": {
        "explanation": "A subset of machine learning using multi-layered neural networks to model complex patterns in large amounts of data.",
        "meaning": "The driving force behind the modern AI revolution, enabling breakthroughs in vision, language, speech, and game-playing.",
        "application": "Image recognition, speech recognition, natural language processing, drug discovery, autonomous vehicles, and recommendation engines.",
    },
    "neural network": {
        "explanation": "A computing system inspired by biological neural networks, consisting of interconnected layers of artificial neurons that learn from data.",
        "meaning": "The fundamental building block of modern AI, capable of approximating any complex function given sufficient capacity and data.",
        "application": "Used in virtually all modern AI systems: classification, regression, generation, control, and representation learning across all domains.",
    },
    "machine learning": {
        "explanation": "A subset of AI that enables systems to automatically learn and improve from experience without being explicitly programmed.",
        "meaning": "The foundational discipline that enables computers to find patterns in data, making predictions and decisions with minimal human intervention.",
        "application": "Fraud detection, medical diagnosis, stock prediction, spam filtering, product recommendations, and countless other data-driven applications.",
    },
    "world model": {
        "explanation": "An internal neural representation that captures the dynamics of an environment, enabling an AI to simulate possible futures and plan actions.",
        "meaning": "A crucial step toward general intelligence, giving AI systems the ability to reason about cause and effect in complex environments.",
        "application": "Autonomous driving simulation, robotics planning, game AI (world models in Minecraft), model-based reinforcement learning, video prediction.",
    },
    "graph neural": {
        "explanation": "Neural network architectures designed to operate on graph-structured data, learning from relationships between interconnected entities.",
        "meaning": "Extends deep learning to non-Euclidean domains like social networks, molecular structures, and knowledge graphs.",
        "application": "Drug discovery and molecular property prediction, social network analysis, recommendation systems, traffic prediction, and knowledge graph reasoning.",
    },
}


def get_default_explanation(keyword: str) -> dict:
    return {
        "explanation": f"{keyword} is an emerging concept in AI research that represents a new direction or technique in the field.",
        "meaning": f"The emergence of {keyword} suggests the AI community is exploring novel approaches to address current limitations in existing methods.",
        "application": f"Based on current research trends, {keyword} is being explored for applications in AI systems, potentially improving efficiency, capability, or robustness of machine learning models.",
    }


GENERIC_WORDS = {
    "just", "like", "make", "made", "making", "get", "got", "getting", "use", "used", "using",
    "say", "said", "says", "going", "go", "went", "come", "came", "coming", "take", "took",
    "taking", "know", "known", "knows", "think", "thinking", "thought", "see", "seen", "seeing",
    "look", "looked", "looking", "want", "wanted", "wanting", "give", "gave", "given", "giving",
    "find", "found", "finding", "tell", "told", "telling", "work", "worked", "working", "works",
    "seem", "seemed", "seems", "seeming", "ask", "asked", "asking", "try", "tried", "trying",
    "leave", "left", "leaving", "call", "called", "calling", "need", "needs", "needed", "needing",
    "feel", "feels", "feeling", "felt", "put", "puts", "putting", "mean", "means", "meant",
    "keep", "keeps", "keeping", "let", "lets", "letting", "begin", "begins", "began", "begun",
    "show", "shows", "showed", "shown", "hear", "hears", "hearing", "heard",
    "run", "runs", "ran", "running", "move", "moves", "moving", "moved", "live", "lives",
    "living", "lived", "bring", "brings", "bringing", "brought", "happen", "happens", "happened",
    "write", "writes", "writing", "wrote", "written", "provide", "provides", "providing",
    "consider", "considers", "considering", "appear", "appears", "appearing", "appeared",
    "exist", "exists", "existing", "existed", "lead", "leads", "leading", "led",
    "learn", "learns", "learning", "learned", "change", "changes", "changing", "changed",
    "include", "includes", "including", "included", "become", "becomes", "becoming", "became",
    "develop", "develops", "developing", "developed", "understand", "understands", "understanding",
    "help", "helps", "helping", "helped", "follow", "follows", "following", "followed",
    "set", "sets", "setting", "grow", "grows", "growing", "grew", "form", "forms", "forming",
    "formed", "play", "plays", "playing", "played", "result", "results", "resulting", "resulted",
    "support", "supports", "supporting", "supported", "present", "presents", "presenting",
    "increase", "increases", "increasing", "increased", "reduce", "reduces", "reducing", "reduced",
    "allow", "allows", "allowing", "allowed", "require", "requires", "requiring", "required",
    "enable", "enables", "enabling", "enabled", "improve", "improves", "improving", "improved",
    "achieve", "achieves", "achieving", "achieved", "propose", "proposes", "proposing", "proposed",
    "address", "addresses", "addressing", "addressed", "suggest", "suggests", "suggesting",
    "perform", "performs", "performing", "performed", "apply", "applies", "applying", "applied",
    "train", "trains", "training", "trained", "test", "tests", "testing", "tested",
    "evaluate", "evaluates", "evaluating", "evaluated",
    "way", "ways", "thing", "things", "part", "parts", "kind", "kinds", "type", "types",
    "much", "more", "most", "less", "least", "same", "different", "other", "another",
    "still", "already", "yet", "always", "never", "ever", "often", "sometimes",
    "here", "there", "every", "own", "very", "too", "also", "well",
    "back", "even", "much", "something", "anything", "nothing", "everything",
    "year", "years", "day", "days", "time", "times", "week", "weeks", "month", "months",
    "number", "numbers", "level", "levels", "area", "areas", "case", "cases", "point", "points",
    "company", "companies", "people", "world", "way", "way", "part", "parts",
    "version", "versions", "user", "users", "system", "systems", "data", "information",
    "research", "technology", "technologies", "application", "applications",
    "approach", "approaches", "method", "methods", "process", "processes",
    "problem", "problems", "solution", "solutions", "task", "tasks", "feature", "features",
    "value", "values", "quality", "performance", "accuracy", "efficiency",
    "issue", "issues", "challenge", "challenges", "benefit", "benefits", "limitation", "limitations",
    "field", "fields", "domain", "domains", "context", "contexts", "scope", "scopes",
    "mechanism", "mechanisms", "strategy", "strategies", "technique", "techniques",
    "tool", "tools", "platform", "platforms", "framework", "frameworks",
    "contribute", "contributes", "contributing", "contributed", "demonstrate",
    "discuss", "discusses", "discussing", "discussed",
    "highlight", "highlights", "highlighting", "highlighted",
    "compare", "compares", "comparing", "compared", "analyze", "analyzes", "analyzing", "analyzed",
    "examine", "examines", "examining", "examined", "investigate", "investigates", "investigating",
    "explore", "explores", "exploring", "explored", "focus", "focuses", "focusing", "focused",
    "extend", "extends", "extending", "extended", "combine", "combines", "combining", "combined",
    "integrate", "integrates", "integrating", "integrated", "generate", "generates", "generating",
    "produce", "produces", "producing", "produced", "capture", "captures", "capturing", "captured",
    "handle", "handles", "handling", "handled", "manage", "manages", "managing", "managed",
    "leverage", "leverages", "leveraging", "leveraged", "deploy", "deploys", "deploying", "deployed",
    "scale", "scales", "scaling", "scaled", "optimize", "optimizes", "optimizing", "optimized",
    "automate", "automates", "automating", "automated",
    "across", "among", "along", "within", "without", "about", "beyond", "despite", "regarding",
    "including", "excluding", "various", "multiple", "numerous", "significant", "substantial",
    "considerable", "notable", "remarkable", "extensive", "widespread", "growing", "increasing",
    "emerging", "novel", "recent", "current", "existing", "future", "potential", "possible",
    "critical", "crucial", "essential", "important", "key", "major", "primary", "fundamental",
    "main", "core", "central", "vital", "necessary", "significant",
    "effective", "efficient", "robust", "flexible", "scalable", "reliable", "accurate",
    "comprehensive", "systematic", "thorough", "extensive",
    "popular", "widely", "commonly", "increasingly", "rapidly", "quickly",
}


def extract_keywords(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()
    filtered = []
    for t in tokens:
        t = t.strip("-_")
        if len(t) < 3:
            continue
        if t.isdigit():
            continue
        if t in STOPWORDS or t in GENERIC_WORDS:
            continue
        filtered.append(t)

    # extract technical bigrams first
    bigram_keywords = set()
    for bigram in TECH_BIGRAMS:
        if bigram in text:
            bigram_keywords.add(bigram)

    # extract unigram keywords
    unigram_keywords = set(filtered)

    return list(bigram_keywords | unigram_keywords)


def categorize_keyword(keyword: str) -> str:
    kw = keyword.lower()

    nlp_keywords = {"language model", "transformer", "attention", "nlp", "natural language",
                    "tokenization", "embedding", "semantic", "text generation", "machine translation",
                    "sentiment", "ner", "relation extraction", "question answering", "summarization"}
    cv_keywords = {"vision", "image", "object detection", "segmentation", "convolution",
                   "visual", "video understanding", "pose estimation", "depth estimation",
                   "image generation", "super resolution", "style transfer"}
    rl_keywords = {"reinforcement", "agent", "environment", "reward", "policy", "value",
                   "control", "planning", "navigation", "robotics", "robot"}
    gen_keywords = {"diffusion", "generative", "gan", "vae", "flow", "generation",
                    "synthesis", "image generation", "text-to-image", "text-to-video"}
    sys_keywords = {"distillation", "quantization", "pruning", "compression", "efficient",
                    "sparse", "deployment", "inference", "latency", "throughput"}
    align_keywords = {"alignment", "rlhf", "safety", "bias", "fairness", "interpretability",
                      "explainability", "robustness", "privacy", "federated"}

    if any(k in kw for k in nlp_keywords):
        return "NLP"
    if any(k in kw for k in cv_keywords):
        return "Computer Vision"
    if any(k in kw for k in rl_keywords):
        return "Reinforcement Learning / Robotics"
    if any(k in kw for k in gen_keywords):
        return "Generative AI"
    if any(k in kw for k in sys_keywords):
        return "ML Systems / Efficiency"
    if any(k in kw for k in align_keywords):
        return "AI Safety / Alignment"
    return "General AI / Emerging"


def score_keyword(
    keyword: str,
    overall_freq: int,
    recent_freq: int,
    prev_freq: int,
    source_diversity: int,
    total_papers: int,
    is_bigram: bool,
) -> float:
    # frequency score (normalized)
    freq_score = math.log1p(recent_freq) / math.log1p(max(total_papers, 1))

    # growth score (recent vs historical)
    if prev_freq > 0:
        growth_ratio = recent_freq / prev_freq
        growth_score = min(growth_ratio / 3.0, 1.0)  # cap at 3x growth
    else:
        growth_score = 0.5 if recent_freq > 0 else 0.0  # new keywords get base boost

    # source diversity score
    diversity_score = min(source_diversity / 3.0, 1.0)

    # bigram bonus (more specific = more valuable)
    bigram_bonus = 0.2 if is_bigram else 0.0

    # recency bonus (favor recent strong signals)
    recency_bonus = min(recent_freq / max(overall_freq, 1), 1.0) * 0.2

    score = (freq_score * 0.3 + growth_score * 0.35 + diversity_score * 0.15 + recency_bonus + bigram_bonus)
    return round(score, 4)


async def analyze_papers(papers: list[dict], db_session) -> dict:
    """Analyze scraped papers and extract keywords, trends, and predictions."""
    from backend.models import Keyword, TrendPrediction, ScanRecord
    from sqlalchemy import select, func as sa_func
    import json

    # extract keywords from all papers
    keyword_paper_map = defaultdict(list)  # keyword -> list of paper info
    category_map = defaultdict(set)  # keyword -> set of categories

    for paper in papers:
        title_keywords = extract_keywords(paper["title"])
        abstract_keywords = extract_keywords(paper["abstract"]) if paper.get("abstract") else []

        all_kw = list(set(title_keywords + abstract_keywords))
        cat = paper.get("category", "AI")

        for kw in all_kw:
            keyword_paper_map[kw].append({
                "title": paper["title"],
                "source": paper["source"],
                "source_url": paper["source_url"],
                "category": cat,
            })
            category_map[kw].add(cat)

    # get existing keywords from db
    result = await db_session.execute(select(Keyword))
    existing_keywords = {k.keyword: k for k in result.scalars().all()}

    # prepare weekly time tracking
    now = datetime.now(timezone.utc)
    current_week = now.isocalendar()
    week_key = f"{current_week[0]}-W{current_week[1]:02d}"

    new_keywords = []
    updated_keywords = []
    all_scores = {}

    for kw, papers_list in keyword_paper_map.items():
        if len(kw) < 3 or len(kw) > 80:
            continue

        recent_freq = len(papers_list)
        sources = set(p["source"] for p in papers_list)
        categories = category_map[kw]
        primary_cat = max(set(categories), key=list(categories).count) if categories else "General AI / Emerging"
        is_bigram = kw in TECH_BIGRAMS or " " in kw.strip()

        # determine if it's a bigram for scoring
        is_bigram_kw = " " in kw.strip()

        # get existing record
        existing = existing_keywords.get(kw)

        MIN_SCORE = 0.08  # minimum score to save a keyword

        if existing:
            prev_freq = existing.frequency
            weekly = dict(existing.weekly_counts) if existing.weekly_counts else {}
            prev_total = sum(v for k, v in weekly.items() if k != week_key)

            overall = recent_freq + prev_total
            score = score_keyword(kw, overall_freq=overall, recent_freq=recent_freq,
                                  prev_freq=max(prev_freq, 1), source_diversity=len(sources),
                                  total_papers=len(papers), is_bigram=is_bigram_kw)

            weekly[week_key] = weekly.get(week_key, 0) + recent_freq

            existing.frequency = prev_freq + recent_freq
            existing.trend_score = score
            existing.is_trending = score > 0.25 and overall > 3
            existing.is_emerging = score > 0.2 and overall <= 5
            existing.weekly_counts = weekly
            existing.source = ",".join(sources)
            if existing.category == "General" and primary_cat != "General":
                existing.category = primary_cat
            updated_keywords.append(existing)
            all_scores[kw] = score
        else:
            score = score_keyword(kw, overall_freq=recent_freq, recent_freq=recent_freq,
                                  prev_freq=0, source_diversity=len(sources),
                                  total_papers=len(papers), is_bigram=is_bigram_kw)

            if score < MIN_SCORE:
                continue

            explanation_data = AI_EXPLANATIONS.get(kw, get_default_explanation(kw))

            kw_obj = Keyword(
                keyword=kw,
                category=primary_cat,
                explanation=explanation_data["explanation"],
                meaning=explanation_data["meaning"],
                application=explanation_data["application"],
                source=",".join(sources),
                frequency=recent_freq,
                trend_score=score,
                is_trending=score > 0.25 and recent_freq > 2,
                is_emerging=True,
                related_keywords=[],
                weekly_counts={week_key: recent_freq},
            )
            new_keywords.append(kw_obj)
            all_scores[kw] = score

    # persist to database
    for kw in new_keywords:
        db_session.add(kw)
    for kw in updated_keywords:
        db_session.add(kw)
    await db_session.flush()

    # refresh to get IDs
    for kw in new_keywords:
        await db_session.refresh(kw)
    for kw in updated_keywords:
        await db_session.refresh(kw)

    # build related keywords using co-occurrence
    all_kw_objects = {k.keyword: k for k in new_keywords + updated_keywords}
    if all_kw_objects:
        # simple co-occurrence: keywords appearing from same papers
        keyword_cooc = defaultdict(Counter)
        for paper in papers:
            pk = set(extract_keywords(paper["title"]) + extract_keywords(paper.get("abstract", "")))
            pk = {k for k in pk if k in all_kw_objects and len(k) >= 3}
            for k1 in pk:
                for k2 in pk:
                    if k1 < k2:
                        keyword_cooc[k1][k2] += 1
                        keyword_cooc[k2][k1] += 1

        for kw_name, kw_obj in all_kw_objects.items():
            related = [k for k, c in keyword_cooc.get(kw_name, Counter()).most_common(5) if c > 0]
            if related:
                kw_obj.related_keywords = related

    # generate trend predictions
    predictions = await generate_predictions(all_scores, keyword_paper_map, db_session)

    return {
        "keywords_found": len(new_keywords) + len(updated_keywords),
        "new_keywords": len(new_keywords),
        "predictions_made": len(predictions),
    }


async def generate_predictions(
    scores: dict[str, float],
    keyword_paper_map: dict[str, list],
    db_session,
) -> list:
    """Generate trend predictions based on keyword analysis."""
    from backend.models import TrendPrediction
    import json

    # sort keywords by score
    sorted_kw = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_keywords = [k for k, s in sorted_kw[:20] if s > 0.2]

    if len(top_keywords) < 3:
        return []

    predictions = []

    # categorize top keywords
    categories = defaultdict(list)
    for kw in top_keywords:
        cat = categorize_keyword(kw)
        categories[cat].append(kw)

    # generate prediction for each category with strong signals
    prediction_templates = {
        "NLP": {
            "title": "NLP Foundation Model Innovation",
            "description": "Research in NLP is increasingly focusing on {keywords}. This cluster suggests the next wave of language models will prioritize efficiency, reasoning, and multimodal integration over pure scale.",
            "impact": "high",
            "horizon": "short-term",
        },
        "Computer Vision": {
            "title": "Visual AI Breakthrough Cycle",
            "description": "Advances in {keywords} indicate computer vision is undergoing a transformer-driven renaissance, with diffusion and foundation models enabling unprecedented generalization capabilities.",
            "impact": "high",
            "horizon": "short-term",
        },
        "Generative AI": {
            "title": "Generative AI Expansion Beyond Images",
            "description": "The rise of {keywords} points to generative AI expanding into video, 3D, music, and scientific domains, with diffusion models becoming the dominant paradigm.",
            "impact": "high",
            "horizon": "short-term",
        },
        "Reinforcement Learning / Robotics": {
            "title": "Embodied AI and Robotics Acceleration",
            "description": "Growing focus on {keywords} signals that AI is moving from digital to physical worlds, with foundation models being adapted for robotic control and autonomous systems.",
            "impact": "high",
            "horizon": "medium-term",
        },
        "ML Systems / Efficiency": {
            "title": "AI Efficiency Revolution",
            "description": "Intensive research in {keywords} shows the field is prioritizing making AI systems smaller, faster, and more deployable, enabling edge AI and reducing environmental impact.",
            "impact": "medium",
            "horizon": "short-term",
        },
        "AI Safety / Alignment": {
            "title": "AI Safety Becoming Mainstream",
            "description": "Increased attention to {keywords} reflects growing industry and research focus on ensuring AI systems are safe, aligned, and beneficial as capabilities rapidly advance.",
            "impact": "high",
            "horizon": "long-term",
        },
        "General AI / Emerging": {
            "title": "Emerging AI Frontiers",
            "description": "Novel concepts like {keywords} indicate the field is exploring fundamentally new approaches, potentially leading to paradigm shifts in how AI systems are designed and trained.",
            "impact": "medium",
            "horizon": "medium-term",
        },
    }

    for cat, kws in categories.items():
        if len(kws) < 2:
            continue

        template = prediction_templates.get(cat, prediction_templates["General AI / Emerging"])
        kw_list = ", ".join(kws[:4])
        keyword_str = f"'{kws[0]}'" if len(kws) == 1 else f"'{kws[0]}' and '{kws[1]}'" if len(kws) == 2 else f"'{kws[0]}', '{kws[1]}', and related areas"
        description = template["description"].format(keywords=kw_list)
        avg_score = sum(scores[k] for k in kws) / len(kws)

        pred = TrendPrediction(
            title=template["title"],
            description=description,
            category=cat,
            confidence=round(avg_score, 2),
            keywords_involved=kws[:6],
            predicted_impact=template["impact"],
            time_horizon=template["horizon"],
        )
        db_session.add(pred)
        predictions.append(pred)

    await db_session.flush()
    return predictions
