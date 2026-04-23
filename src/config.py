"""Alert definitions and PubMed search module queries.

═══════════════════════════════════════════════════════════════════════════
THIS TEMPLATE SHIPS WITH PSYCHIATRY + CLINICAL INFORMATICS DEFAULTS.
Replace with your own field — see README § "Adapting to a non-psychiatry field".

Main things to change:
  1. PSYCH           → your domain (e.g., rename to CARDIO, NEURO, ONCOLOGY)
  2. JOURNAL_TOP_PSYCH → your field's top journals
  3. METHODS subsections (EHR/Wearables/AI/DigPhen) → your methods of interest
  4. DB_ABCD / DB_EPIC_COSMOS / DB_ALL_OF_US → your research databases
  5. _ISSN_LIST → populate if you have JCR access (see DESIGN.md § ISSN Whitelist)

The two-layer design (module definitions here, alert strategies in ALERTS
below) means you never touch API code in pubmed.py / medrxiv.py / etc.
═══════════════════════════════════════════════════════════════════════════
"""

# ---------------------------------------------------------------------------
# Journal filters
# ---------------------------------------------------------------------------

JOURNAL_TOP_MED = (
    '"JAMA Pediatr"[journal] OR "JAMA Intern Med"[journal] '
    'OR "JAMA Netw Open"[journal] OR "JAMA"[journal] '
    'OR "Lancet Child Adolesc Health"[journal] OR "Lancet Digit Health"[journal] '
    'OR "Lancet Reg Health Eur"[journal] OR "Lancet Public Health"[journal] '
    'OR "Lancet Glob Health"[journal] OR "Lancet"[journal] '
    'OR "BMJ"[journal] OR "N Engl J Med"[journal] '
    'OR "Nat Med"[journal] '  # npj Digit Med moved to JOURNAL_CLINICAL_INFORMATICS
    'OR "J CLIN INVEST"[journal] OR "EClinicalMedicine"[journal] '
    'OR "Science"[journal] OR "Nature"[journal] OR "Cell"[journal] '
    'OR "AM J PUBLIC HEALTH"[journal] OR "J CLIN EPIDEMIOL"[journal] '
    'OR "EUR J EPIDEMIOL"[journal] OR "AM J EPIDEMIOL"[journal]'
)

# Clinical informatics and digital health journals
JOURNAL_CLINICAL_INFORMATICS = (
    '"npj Digit Med"[journal] '
    'OR "J Am Med Inform Assoc"[journal] '
    'OR "J Biomed Inform"[journal] '
    'OR "Artif Intell Med"[journal] '
    'OR "IEEE J Biomed Health Inform"[journal] '
    'OR "JMIR Ment Health"[journal]'
)

JOURNAL_TOP_PSYCH = (
    '"World Psychiatry"[journal] OR "Lancet Psychiatry"[journal] '
    'OR "JAMA Psychiatry"[journal] OR "Am J Psychiatry"[journal] '
    'OR "Mol Psychiatry"[journal] OR "Biol Psychiatry"[journal] '
    'OR "Br J Psychiatry"[journal] OR "Curr Opin Psychiatry"[journal] '
    'OR "Eur Psychiatry"[journal] OR "J Behav Addict"[journal] '
    'OR "Evid Based Ment Health"[journal] OR "Nat Ment Health"[journal] '
    'OR "Nat Rev Psychol"[journal] OR "Clin Psychol Rev"[journal] '
    'OR "Translational Psychiatry"[journal] OR "Nat Hum Behav"[journal] '
    'OR "J Am Acad Child Adolesc Psychiatry"[journal] '
    # Added journals
    'OR "Psychol Med"[journal] OR "Child Adolesc Ment Health"[journal] '
    'OR "Curr Opin Psychol"[journal] OR "Curr Psychiatry Rep"[journal]'
)

# ISSN whitelist — quality floor for Section 1 (Psych × Methods subsections)
#
# Populate this list with ISSNs from journals meeting your IF cutoff (e.g., IF >= 7).
#
# Data comes from Clarivate JCR (institutional subscription). JCR terms prohibit
# redistribution of the dataset, so this template ships empty. Section 1 will fall
# back to TopMed ∪ TopPsych ∪ ClinicalInformatics journals only — still works,
# just with less breadth.
#
# To add your own whitelist:
#   1. Download JCR <year> Excel from your university's Clarivate subscription.
#   2. Filter rows to your IF cutoff.
#   3. Paste ISSNs below as a pipe-separated string.
#
# See DESIGN.md > "ISSN whitelist" for rationale.

_ISSN_LIST = ""  # e.g., "0028-4793|1533-4406|..."

ISSN_WHITELIST = (
    " OR ".join(f'"{issn}"[ISSN]' for issn in _ISSN_LIST.split("|") if issn)
    if _ISSN_LIST
    else ""
)

# ---------------------------------------------------------------------------
# Domain modules
# ---------------------------------------------------------------------------

PSYCH = (
    '"Mental Health"[MeSH] OR "Mental Disorders"[MeSH] OR psych*[tiab] OR '
    '"internalizing symptom*"[tiab] OR "externalizing symptom*"[tiab] OR '
    '"internalizing behavi*"[tiab] OR "externalizing behavi*"[tiab] OR '
    '"internalizing problem*"[tiab] OR "externalizing problem*"[tiab] OR '
    '"Mood Disorders"[MeSH] OR "Depressive Disorder"[MeSH] OR "Depression"[MeSH] OR '
    '"Major Depressive Disorder"[MeSH] OR "Dysthymic Disorder"[MeSH] OR '
    'depress*[tiab] OR bipolar[tiab] OR manic[tiab] OR mania[tiab] OR mood disorder*[tiab] OR '
    '"Anxiety Disorders"[MeSH] OR anxiet*[tiab] OR "generalized anxiety"[tiab] OR phobia*[tiab] OR '
    '"Stress Disorders, Traumatic"[MeSH] OR "Stress Disorders, Post-Traumatic"[MeSH] OR '
    'PTSD[tiab] OR '
    '"Suicide"[MeSH] OR "Suicidal Ideation"[MeSH] OR "Self-Injurious Behavior"[MeSH] OR '
    'suicid*[tiab] OR "self-harm"[tiab] OR "self-injury"[tiab] OR NSSI[tiab] OR '
    '"Attention Deficit Disorder with Hyperactivity"[MeSH] OR "Conduct Disorder"[MeSH] OR '
    '"Oppositional Defiant Disorder"[MeSH] OR ADHD[tiab] OR "attention deficit"[tiab] OR '
    'hyperactiv*[tiab] OR "conduct disorder"[tiab] OR "oppositional defiant"[tiab] OR '
    '"Aggression"[MeSH] OR aggression[tiab] OR "aggress* behav*"[tiab] OR '
    '"disruptive behav*"[tiab] OR impuls*[tiab] OR neurodevelop*[tiab] OR '
    '"emotion* dysregulat*"[tiab] OR "emotion* regulat*"[tiab]'
)

# ---------------------------------------------------------------------------
# Methods sub-modules (4 subsections for new architecture)
# ---------------------------------------------------------------------------

# Subsection 1: EHR (electronic health records + multimodal data integration)
EHR_METHODS = (
    '"Electronic Health Records"[MeSH] OR "electronic health record*"[tiab] OR "EHR"[tiab] OR '
    '"electronic medical record*"[tiab] OR "EMR"[tiab] OR '
    '"clinical informatics"[tiab] OR '
    '"real-world evidence"[tiab] OR "real-world data"[tiab] OR '
    '"claims data"[tiab] OR "phenotyping algorithm*"[tiab] OR '
    '"clinical note*"[tiab] OR "unstructured clinical data"[tiab] OR '
    '"clinical data repositor*"[tiab] OR "data warehous*"[tiab] OR '
    '"Multimodal"[tiab] OR "Data Fusion"[tiab] OR "Integrated Data"[tiab] OR "Multisource Data"[tiab]'
)

# Subsection 2: Wearables (wearable devices + sensor fusion)
WEARABLES_METHODS = (
    '"Wearable Electronic Devices"[MeSH] OR "Monitoring, Physiologic"[MeSH] OR '
    '"wearable*"[tiab] OR "smartwatch"[tiab] OR "smart device*"[tiab] OR "smart ring"[tiab] OR '
    '"smartphone sensor"[tiab] OR "fitbit"[tiab] OR '
    '"accelerom*"[tiab] OR "actigraphy"[tiab] OR '
    '"mobile sensor"[tiab] OR "sensor-based"[tiab] OR '
    '"GPS tracking"[tiab] OR "location tracking"[tiab] OR '
    '"Sensor Fusion"[tiab] OR "multimodal sensing"[tiab]'
)

# Subsection 3: AI/ML (machine learning, NLP, computational methods)
AI_METHODS = (
    '"Machine Learning"[MeSH] OR "Artificial Intelligence"[MeSH] OR "Natural Language Processing"[MeSH] OR '
    '"Machine Learning"[tiab] OR "Artificial Intelligence"[tiab] OR "AI-based"[tiab] OR "ML-based"[tiab] OR '
    '"Deep Learning"[tiab] OR "Neural Network*"[tiab] OR '
    '"Supervised Learning"[tiab] OR "Unsupervised Learning"[tiab] OR "Reinforcement Learning"[tiab] OR '
    '"Predictive Model*"[tiab] OR "Random Forest"[tiab] OR "Decision Tree"[tiab] OR '
    '"Support Vector Machine"[tiab] OR "Gradient Boosting"[tiab] OR "XGBoost"[tiab] OR '
    '"Computational Method*"[tiab] OR "Algorithm*"[tiab] OR "Data-Driven"[tiab] OR "Modeling Approach*"[tiab] OR '
    '"large language model*"[tiab] OR "LLM"[tiab] OR "GPT"[tiab] OR "ChatGPT"[tiab] OR '
    '"transformer*"[tiab] OR "foundation model*"[tiab] OR '
    '"Clinical Text Mining"[tiab] OR "Clinical Notes"[tiab] OR "Text Classification"[tiab] OR '
    '"natural language processing"[tiab] OR "NLP"[tiab] OR "text mining"[tiab] OR '
    '"functional data analysis"[tiab] OR "functional principal component*"[tiab] OR "FPCA"[tiab] OR '
    '"time series"[tiab] OR "time-series"[tiab] OR "temporal pattern*"[tiab] OR '
    '"precision psych*"[tiab] OR "computational psych*"[tiab]'
)

# Subsection 4: Digital Phenotyping (EMA, passive sensing, digital biomarkers)
DIGITAL_PHENOTYPING_METHODS = (
    '"Ecological Momentary Assessment"[MeSH] OR "Remote Sensing Technology"[MeSH] OR '
    '"ecological momentary assessment"[tiab] OR "EMA"[tiab] OR "experience sampling"[tiab] OR '
    '"real-time assessment"[tiab] OR "real-time monitoring"[tiab] OR "real-time data"[tiab] OR '
    '"momentary data"[tiab] OR "daily diary"[tiab] OR '
    '"intensive longitudinal"[tiab] OR "high-frequency data"[tiab] OR '
    '"digital phenotyp*"[tiab] OR '
    '"passive sens*"[tiab] OR "passive data"[tiab] OR '
    '"digital biomarker*"[tiab] OR '
    '"digital monitor*"[tiab] OR '
    '"ambient data"[tiab] OR "sensor data"[tiab] OR '
    '"digital trace*"[tiab] OR "screenomics"[tiab] OR "app usage"[tiab] OR '
    '"behavioral monitoring"[tiab] OR "emotion recognition"[tiab] OR '
    '"context-aware"[tiab] OR "contextual sens*"[tiab] OR '
    '"Just-In-Time Adaptive Intervention*"[tiab] OR "adaptive intervention*"[tiab]'
)

# Combined Methods_Focus for backward compatibility
METHODS_FOCUS = f"({EHR_METHODS}) OR ({WEARABLES_METHODS}) OR ({AI_METHODS}) OR ({DIGITAL_PHENOTYPING_METHODS})"

# List of methods subsections in order (for iteration)
METHODS_SUBSECTIONS = [
    ("EHR", EHR_METHODS),
    ("Wearables", WEARABLES_METHODS),
    ("AI/ML", AI_METHODS),
    ("Digital Phenotyping", DIGITAL_PHENOTYPING_METHODS),
]

# ---------------------------------------------------------------------------
# Databases module
#
# Each entry defines a PubMed query for a specific public research database
# or cohort that you want to track weekly. Keep queries specific (full
# database name in quotes) — broad terms will drown the weekly section.
#
# The three below are concrete examples from child psychiatry + EHR +
# population-scale research. Replace with databases relevant to your field.
# Other common options: UK Biobank, NHANES, MIMIC-III / MIMIC-IV, CPRD.
# ---------------------------------------------------------------------------

DB_ABCD = '"adolescent brain cognitive development"[tiab] OR "ABCD Study"[tiab]'
DB_EPIC_COSMOS = '"Epic Cosmos"[tiab]'
DB_ALL_OF_US = '"All of Us"[tiab]'

DATABASES = f"{DB_ABCD} OR {DB_EPIC_COSMOS} OR {DB_ALL_OF_US}"

# ---------------------------------------------------------------------------
# Alert definitions (new 3-section architecture)
# ---------------------------------------------------------------------------

# All journals combined for Section 1
_ALL_JOURNALS = f"({JOURNAL_TOP_MED}) OR ({JOURNAL_TOP_PSYCH}) OR ({JOURNAL_CLINICAL_INFORMATICS}) OR ({ISSN_WHITELIST})"

# Section 3 journals (no ISSN whitelist - too many)
_SECTION3_JOURNALS = f"({JOURNAL_TOP_MED}) OR ({JOURNAL_CLINICAL_INFORMATICS})"

# Section 2 journals: Top Med + Clinical Informatics (no ISSN whitelist)
_SECTION2_JOURNALS_WITH_FILTER = f"({JOURNAL_TOP_MED}) OR ({JOURNAL_CLINICAL_INFORMATICS})"

ALERTS = [
    # =========================================================================
    # SECTION 1: Psych × Methods Focus (priority 1.x - subsections)
    # All journals × Psych × Methods, split by methods subsection
    # =========================================================================
    {
        "name": "EHR",
        "query": f"({_ALL_JOURNALS}) AND ({PSYCH}) AND ({EHR_METHODS})",
        "days_back": 1,
        "priority": 1.1,
        "daily": True,
        "sunday_only": False,
        "section": "Psych × Methods",
        "subsection_order": 1,
    },
    {
        "name": "Wearables",
        "query": f"({_ALL_JOURNALS}) AND ({PSYCH}) AND ({WEARABLES_METHODS})",
        "days_back": 1,
        "priority": 1.2,
        "daily": True,
        "sunday_only": False,
        "section": "Psych × Methods",
        "subsection_order": 2,
    },
    {
        "name": "AI/ML",
        "query": f"({_ALL_JOURNALS}) AND ({PSYCH}) AND ({AI_METHODS})",
        "days_back": 1,
        "priority": 1.3,
        "daily": True,
        "sunday_only": False,
        "section": "Psych × Methods",
        "subsection_order": 3,
    },
    {
        "name": "Digital Phenotyping",
        "query": f"({_ALL_JOURNALS}) AND ({PSYCH}) AND ({DIGITAL_PHENOTYPING_METHODS})",
        "days_back": 1,
        "priority": 1.4,
        "daily": True,
        "sunday_only": False,
        "section": "Psych × Methods",
        "subsection_order": 4,
    },
    # =========================================================================
    # SECTION 2: General Psychiatry (priority 2) - NO SUBSECTIONS
    # Top Psych (all) + (Top Med + Clinical Informatics) × Psych
    # =========================================================================
    {
        "name": "General Psychiatry",
        "query": f"({JOURNAL_TOP_PSYCH}) OR (({_SECTION2_JOURNALS_WITH_FILTER}) AND ({PSYCH}))",
        "days_back": 1,
        "priority": 2,
        "daily": True,
        "sunday_only": False,
        "section": "General Psychiatry",
        "subsection_order": 1,
    },
    # =========================================================================
    # SECTION 3: General Methods (priority 3.x - subsections)
    # (Top Med + Clinical Informatics) × Methods, no Psych requirement
    # =========================================================================
    {
        "name": "Methods_EHR",
        "display_name": "EHR",
        "query": f"({_SECTION3_JOURNALS}) AND ({EHR_METHODS})",
        "days_back": 1,
        "priority": 3.1,
        "daily": True,
        "sunday_only": False,
        "section": "General Methods",
        "subsection_order": 1,
    },
    {
        "name": "Methods_Wearables",
        "display_name": "Wearables",
        "query": f"({_SECTION3_JOURNALS}) AND ({WEARABLES_METHODS})",
        "days_back": 1,
        "priority": 3.2,
        "daily": True,
        "sunday_only": False,
        "section": "General Methods",
        "subsection_order": 2,
    },
    {
        "name": "Methods_AI/ML",
        "display_name": "AI/ML",
        "query": f"({_SECTION3_JOURNALS}) AND ({AI_METHODS})",
        "days_back": 1,
        "priority": 3.3,
        "daily": True,
        "sunday_only": False,
        "section": "General Methods",
        "subsection_order": 3,
    },
    {
        "name": "Methods_DigitalPhenotyping",
        "display_name": "Digital Phenotyping",
        "query": f"({_SECTION3_JOURNALS}) AND ({DIGITAL_PHENOTYPING_METHODS})",
        "days_back": 1,
        "priority": 3.4,
        "daily": True,
        "sunday_only": False,
        "section": "General Methods",
        "subsection_order": 4,
    },
    # =========================================================================
    # WEEKLY: Research Databases (priority 4.x - subsections by database)
    # Each database is a subsection, PubMed only (preprints handled separately)
    # =========================================================================
    {
        "name": "ABCD Study",
        "query": f"({DB_ABCD})",
        "days_back": 7,
        "priority": 4.1,
        "daily": False,
        "sunday_only": True,
        "section": "Research Databases",
        "subsection_order": 1,
    },
    {
        "name": "Epic Cosmos",
        "query": f"({DB_EPIC_COSMOS})",
        "days_back": 7,
        "priority": 4.2,
        "daily": False,
        "sunday_only": True,
        "section": "Research Databases",
        "subsection_order": 2,
    },
    {
        "name": "All of Us",
        "query": f"({DB_ALL_OF_US})",
        "days_back": 7,
        "priority": 4.3,
        "daily": False,
        "sunday_only": True,
        "section": "Research Databases",
        "subsection_order": 3,
    },
]

# Database keywords for preprint search
DATABASE_KEYWORDS = {
    "ABCD Study": ["ABCD Study", "adolescent brain cognitive development"],
    "Epic Cosmos": ["Epic Cosmos"],
    "All of Us": ["All of Us"],
}
