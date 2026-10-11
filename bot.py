"""
SONIC RESOURCE FACTORY
Single-file Telegram AI educational-resource generator.

Install:
    pip install -r requirements.txt

Run:
    python bot.py

The bot uses an OpenAI-compatible chat-completions endpoint.  The endpoint,
model, and credentials are deliberately configured at the top of this file.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
import zipfile
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Optional

import aiohttp
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# ============================================================================ #
# EDITABLE CONFIGURATION
# ============================================================================ #

# Keep credentials out of source control. Paste them locally only when deploying.
BOT_TOKEN = ""
AI_API_KEY = ""
AI_BASE_URL = "https://router.bynara.id/v1"

# SINGLE model, SINGLE key only — no rotation, no mixing.
# (Mixing models mid-batch made notes/quizzes inconsistent in style and quality.)
AI_MODEL = "agnes-2.5-flash"

OWNER_IDS = [
    8226637107
]

FORCE_JOIN_CHANNEL = "https://t.me/+NGUSfa7ns8c4OTll"

MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "3"))  # lower this (e.g. 1 or 2) if you're on a slow/unstable connection — 3 parallel AI calls fighting over thin bandwidth is a common cause of repeated TimeoutErrors on the same heavy topics
MAX_AI_RETRIES = 6  # weak/unstable networks need more attempts before a job is given up on
PROGRESS_UPDATE_SECONDS = 3.0
DATABASE_PATH = "sonic_factory.sqlite3"
OUTPUT_DIR = "OUTPUT"
SOURCE_DIR = "SOURCES"
HTTP_TIMEOUT_SECONDS = 240

# Academy branding — shown on the hero of every generated HTML page and on the
# auto-built hub/index pages (the "PrepGridOfficial Academy" feel).
ACADEMY_NAME = "PrepGridOfficial Academy"
ACADEMY_TAGLINE = "Dream big. Prepare daily. Crack it."
HUB_FILENAME = "index.html"
QUESTION_SIMILARITY_THRESHOLD = 0.88

# Fallback question count ONLY used when an exam has no pattern-based count below.
DEFAULT_TEST_QUESTIONS = 30
DEFAULT_QUESTION_COUNT = DEFAULT_TEST_QUESTIONS
MINIMUM_MCQ_OPTIONS = 4

# Every quiz-style file (anything except Full-Mock, which follows the exam's
# real official paper size) must have at least this many questions — never a
# thin 10-15 question file passed off as a full resource.
MINIMUM_QUIZ_QUESTIONS = 30

# How many questions a Topic-Test / Chapter-Test should contain relative to a
# Full-Mock (which always uses the exam's real total question count below).
TOPIC_TEST_QUESTIONS = 30
CHAPTER_TEST_QUESTIONS = 30
SUBJECT_TEST_QUESTIONS = 50


# ============================================================================ #
# EDITABLE EXAM BLUEPRINTS
# ============================================================================ #

VERIFY_REQUIRED = "VERIFY_REQUIRED"


def blueprint(
    name: str,
    authority: str,
    subjects: list[str],
    languages: list[str],
    recommended_language: str,
    topics: Optional[dict[str, list[str]]] = None,
    resources: Optional[list[str]] = None,
    full_mock_questions: Optional[int] = None,
    pattern_note: str = VERIFY_REQUIRED,
    subject_distribution: Optional[dict[str, int]] = None,
) -> dict[str, Any]:
    """Create an editable blueprint. `full_mock_questions` drives the exact
    number of questions a Full-Mock file for this exam will contain — set it
    only when the official count is verified (see pattern_note otherwise).
    `subject_distribution` (e.g. {"Physics":45,"Chemistry":45,"Biology":90})
    is what Full-Syllabus-Mock uses to build one real cross-subject paper in
    the exam's official proportion — only set it when that split is verified."""
    topics = topics or {subject: ["Add topics in EXAM_CONFIG"] for subject in subjects}
    return {
        "exam_name": name,
        "authority": authority,
        "subjects": subjects,
        "syllabus": VERIFY_REQUIRED,
        "chapters": VERIFY_REQUIRED,
        "topics": topics,
        "languages": languages,
        "recommended_language": recommended_language,
        "exam_pattern": pattern_note,
        "sections": VERIFY_REQUIRED,
        "question_count": VERIFY_REQUIRED,
        "duration": VERIFY_REQUIRED,
        "marking_scheme": VERIFY_REQUIRED,
        "question_types": VERIFY_REQUIRED,
        "difficulty_distribution": VERIFY_REQUIRED,
        "full_mock_questions": full_mock_questions,
        "subject_distribution": subject_distribution,
        "recommended_resources": resources
        or ["Notes", "Quick-Revision", "PYQ", "Practice", "Topic-Test", "Chapter-Test", "Full-Mock", "Flashcards"],
    }


# Add or edit exams here. Chapter lists below are the standard, widely-published
# syllabus outline for each exam. Where a specific number/marking detail is not
# certain (it changes year to year), the platform tells the AI to say so instead
# of inventing it (see GENERATOR_SYSTEM) — always cross-check the latest official
# notification before an exam.
EXAM_CONFIG: dict[str, dict[str, Any]] = {
    "NEET": blueprint(
        "NEET", "National Testing Agency (NTA)",
        ["Physics", "Chemistry", "Biology"], ["Gujarati", "Hindi", "English"], "English",
        {
            "Physics": [
                "Physical World and Measurement", "Kinematics", "Laws of Motion",
                "Work, Energy and Power", "Motion of System of Particles and Rigid Body",
                "Gravitation", "Mechanical Properties of Solids", "Mechanical Properties of Fluids",
                "Thermal Properties of Matter", "Thermodynamics", "Kinetic Theory of Gases",
                "Oscillations", "Waves", "Electrostatics", "Current Electricity",
                "Moving Charges and Magnetism", "Magnetism and Matter", "Electromagnetic Induction",
                "Alternating Current", "Electromagnetic Waves", "Ray Optics and Optical Instruments",
                "Wave Optics", "Dual Nature of Radiation and Matter", "Atoms", "Nuclei",
                "Semiconductor Electronics",
            ],
            "Chemistry": [
                "Some Basic Concepts of Chemistry", "Structure of Atom",
                "Classification of Elements and Periodicity", "Chemical Bonding and Molecular Structure",
                "States of Matter", "Thermodynamics", "Equilibrium", "Redox Reactions",
                "Hydrogen and s-Block Elements", "p-Block Elements (Group 13 & 14)",
                "Organic Chemistry - Basic Principles", "Hydrocarbons", "Environmental Chemistry",
                "Solid State", "Solutions", "Electrochemistry", "Chemical Kinetics", "Surface Chemistry",
                "p-Block Elements (Group 15-18)", "d and f Block Elements", "Coordination Compounds",
                "Haloalkanes and Haloarenes", "Alcohols, Phenols and Ethers",
                "Aldehydes, Ketones and Carboxylic Acids", "Organic Compounds Containing Nitrogen",
                "Biomolecules", "Polymers", "Chemistry in Everyday Life",
            ],
            "Biology": [
                "Diversity in Living World", "Structural Organisation in Animals and Plants",
                "Cell Structure and Function", "Plant Physiology", "Human Physiology",
                "Reproduction", "Genetics and Evolution", "Biology and Human Welfare",
                "Biotechnology and Its Applications", "Ecology and Environment",
            ],
        },
        ["Notes", "Quick-Revision", "Formula-Sheet", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Full-Syllabus-Mock", "Flashcards", "Revision-Test"],
        full_mock_questions=180,
        subject_distribution={"Physics": 45, "Chemistry": 45, "Biology": 90},
        pattern_note="180 compulsory MCQs (Physics 45, Chemistry 45, Biology/Botany+Zoology 90), 720 marks, 3 hours, +4/-1 negative marking. Confirm against the current-year NTA notification.",
    ),
    "JEE Main": blueprint(
        "JEE Main", "National Testing Agency (NTA)",
        ["Physics", "Chemistry", "Mathematics"], ["English", "Hindi", "Gujarati"], "English",
        {
            "Physics": [
                "Units and Measurement", "Kinematics", "Laws of Motion", "Work Energy and Power",
                "Rotational Motion", "Gravitation", "Properties of Solids and Liquids", "Thermodynamics",
                "Kinetic Theory of Gases", "Oscillations and Waves", "Electrostatics", "Current Electricity",
                "Magnetic Effects of Current and Magnetism", "Electromagnetic Induction and AC",
                "Electromagnetic Waves", "Optics", "Dual Nature of Matter and Radiation",
                "Atoms and Nuclei", "Electronic Devices", "Experimental Skills",
            ],
            "Chemistry": [
                "Basic Concepts in Chemistry", "Atomic Structure", "Chemical Bonding and Molecular Structure",
                "Chemical Thermodynamics", "Solutions", "Equilibrium", "Redox and Electrochemistry",
                "Chemical Kinetics", "Classification of Elements and Periodicity", "p-Block Elements",
                "d and f Block Elements", "Coordination Compounds", "Purification and Characterisation of Organic Compounds",
                "Basic Principles of Organic Chemistry", "Hydrocarbons", "Organic Compounds with Halogens",
                "Organic Compounds with Oxygen", "Organic Compounds with Nitrogen", "Biomolecules and Polymers",
                "Chemistry in Everyday Life", "Principles Related to Practical Chemistry",
            ],
            "Mathematics": [
                "Sets, Relations and Functions", "Complex Numbers and Quadratic Equations",
                "Matrices and Determinants", "Permutations and Combinations", "Binomial Theorem",
                "Sequences and Series", "Limits, Continuity and Differentiability", "Integral Calculus",
                "Differential Equations", "Coordinate Geometry", "Three Dimensional Geometry",
                "Vector Algebra", "Statistics and Probability", "Trigonometry", "Mathematical Reasoning",
            ],
        },
        ["Notes", "Quick-Revision", "Formula-Sheet", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Full-Syllabus-Mock", "Flashcards"],
        full_mock_questions=75,
        subject_distribution={"Physics": 25, "Chemistry": 25, "Mathematics": 25},
        pattern_note="Paper 1 (B.Tech): 75 questions (20 MCQ + 5 numerical per subject), 300 marks, 3 hours, +4/-1 for MCQs, no negative marking for numerical-value questions. Confirm against the current NTA information bulletin.",
    ),
    "JEE Advanced": blueprint(
        "JEE Advanced", "JEE Apex Board / IITs",
        ["Physics", "Chemistry", "Mathematics"], ["English", "Hindi"], "English",
        {
            "Physics": ["Mechanics", "Waves and Thermodynamics", "Electricity and Magnetism",
                        "Optics", "Modern Physics"],
            "Chemistry": ["Physical Chemistry", "Inorganic Chemistry", "Organic Chemistry"],
            "Mathematics": ["Algebra", "Trigonometry", "Analytical Geometry", "Differential Calculus",
                             "Integral Calculus", "Vectors"],
        },
        ["Notes", "Quick-Revision", "Formula-Sheet", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Two papers, 3 hours each, mixed question types (MCQ, multi-correct, numerical, matrix-match); exact question count/marking varies every year — verify from the latest JEE Advanced information brochure.",
    ),
    "GUJCET": blueprint(
        "GUJCET", "Gujarat Secondary and Higher Secondary Education Board (GSEB)",
        ["Physics", "Chemistry", "Mathematics", "Biology"], ["Gujarati", "English"], "Gujarati",
        {
            "Physics": ["Electrostatics", "Current Electricity", "Magnetic Effects of Current", "Electromagnetic Induction",
                        "Optics", "Dual Nature of Matter", "Atoms and Nuclei", "Semiconductor Electronics",
                        "Kinematics", "Laws of Motion", "Work Energy Power", "Gravitation", "Thermodynamics"],
            "Chemistry": ["Solid State", "Solutions", "Electrochemistry", "Chemical Kinetics", "d and f Block Elements",
                          "Coordination Compounds", "Haloalkanes and Haloarenes", "Alcohols Phenols Ethers",
                          "Aldehydes Ketones Carboxylic Acids", "Biomolecules", "Chemical Bonding", "Equilibrium"],
            "Mathematics": ["Relations and Functions", "Matrices and Determinants", "Continuity and Differentiability",
                             "Application of Derivatives", "Integrals", "Differential Equations", "Vectors",
                             "Three Dimensional Geometry", "Probability"],
            "Biology": ["Reproduction", "Genetics and Evolution", "Biology and Human Welfare",
                        "Biotechnology", "Ecology and Environment"],
        },
        ["Notes", "Quick-Revision", "Formula-Sheet", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="MCQ-based, standard 11+12 GSEB syllabus (PCM for engineering stream, PCB for pharmacy/other stream). Verify current question count/duration from the latest GSEB GUJCET notification.",
    ),
    "Gujarat Police Constable": blueprint(
        "Gujarat Police Constable", "Gujarat Police Recruitment Board (Lokrakshak Cadre)",
        ["General Knowledge and Current Affairs", "Gujarati Language", "English Language", "Quantitative Aptitude and Reasoning", "Computer Knowledge"],
        ["Gujarati", "English"], "Gujarati",
        {
            "General Knowledge and Current Affairs": [
                "Indian History and Freedom Movement", "Gujarat History and Culture", "Indian Geography", "Gujarat Geography",
                "Indian Constitution and Polity", "Gujarat Government and Administration", "Economy and Development",
                "General Science", "Environment and Ecology", "Current Affairs and Awards", "Sports and Important Events",
            ],
            "Gujarati Language": ["Gujarati Grammar", "Vocabulary and Synonyms", "Antonyms and Idioms", "Comprehension and Passage", "Literature and Authors"],
            "English Language": ["English Grammar", "Vocabulary", "Synonyms and Antonyms", "Comprehension", "Sentence Correction"],
            "Quantitative Aptitude and Reasoning": [
                "Number System", "Simplification", "Percentage", "Ratio and Proportion", "Average", "Profit Loss and Discount",
                "Simple and Compound Interest", "Time Work and Distance", "Data Interpretation", "Analogy and Classification",
                "Series", "Coding Decoding", "Blood Relations", "Direction and Ranking", "Calendar and Clock", "Statement Reasoning",
            ],
            "Computer Knowledge": ["Computer Fundamentals", "Operating Systems", "Word Processing and Spreadsheets", "Internet and Cyber Safety", "Digital Gujarat Services"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Topic-Test", "Chapter-Test", "Subject-Test", "Full-Mock", "Full-Syllabus-Mock", "Flashcards", "Current-Affairs"],
        full_mock_questions=None,
        pattern_note="Syllabus topics are an editable preparation registry. Verify the current Gujarat Police Recruitment Board notification for post, paper structure, marks, duration and negative marking before publishing as official.",
    ),
    "GSEB / Gujarat Board": blueprint(
        "GSEB / Gujarat Board", "Gujarat Secondary and Higher Secondary Education Board",
        ["Gujarati", "English", "Hindi/Sanskrit", "Mathematics", "Science", "Social Science"],
        ["Gujarati", "English"], "Gujarati",
        {
            "Gujarati": ["Prose (Gadya)", "Poetry (Padya)", "Grammar (Vyakaran)", "Composition (Lekhan)"],
            "English": ["Prose", "Poetry", "Grammar", "Writing Skills", "Comprehension"],
            "Mathematics": ["Number Systems", "Algebra", "Geometry", "Trigonometry", "Mensuration",
                             "Statistics and Probability", "Coordinate Geometry"],
            "Science": ["Chemical Reactions", "Acids Bases and Salts", "Metals and Non-metals", "Carbon Compounds",
                        "Life Processes", "Heredity and Evolution", "Light", "Electricity", "Magnetic Effects",
                        "Natural Resources"],
            "Social Science": ["History (Modern India)", "Civics (Indian Constitution)", "Geography (Resources and Development)",
                                "Economics (Development and Sustainability)"],
        },
        ["Notes", "Quick-Revision", "Formula-Sheet", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Board exam pattern (marks split between MCQ/short/long answer) differs by standard (10/12) and subject — verify the current year's GSEB paper pattern/blueprint.",
    ),
    "GPSC": blueprint(
        "GPSC", "Gujarat Public Service Commission",
        ["General Studies", "Gujarati Language", "English Language"], ["Gujarati", "English"], "Gujarati",
        {
            "General Studies": [
                "Indian History and Freedom Struggle", "History and Culture of Gujarat",
                "Indian and World Geography", "Geography of Gujarat", "Indian Polity and Governance",
                "Panchayati Raj and Local Self-Government", "Indian Economy", "Economy of Gujarat",
                "Science and Technology", "Environment and Ecology", "General Mental Ability and Reasoning",
                "Current Affairs (National, International, Gujarat)", "Gujarat's Culture, Art, Literature and Heritage",
            ],
            "Gujarati Language": ["Grammar", "Vocabulary", "Comprehension", "Essay and Letter Writing"],
            "English Language": ["Grammar", "Vocabulary", "Comprehension", "Precis and Essay Writing"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs", "Answer-Writing"],
        pattern_note="Class 1-2: Prelims (2 objective papers, GS-I & GS-II, 200 marks each, no negative marking) → Mains (descriptive, qualifying Gujarati/English papers + GS/Essay merit papers) → Interview. Exact per-paper question count/duration changes by advertisement — verify the latest GPSC notification.",
    ),
    "UPSC": blueprint(
        "UPSC", "Union Public Service Commission",
        ["General Studies", "CSAT", "Essay", "Optional Subject"], ["Hindi", "English"], "English",
        {
            "General Studies": [
                "Indian Heritage and Culture", "Modern Indian History", "Post-Independence Consolidation",
                "Indian and World Geography", "Indian Polity and Governance", "Indian Constitution",
                "Indian Economy and Planning", "Social Justice", "Science and Technology",
                "Environment and Biodiversity", "Disaster Management", "Internal Security",
                "International Relations", "Ethics, Integrity and Aptitude", "Current Affairs",
            ],
            "CSAT": ["Comprehension", "Interpersonal and Communication Skills", "Logical Reasoning and Analytical Ability",
                      "Decision Making and Problem Solving", "General Mental Ability", "Basic Numeracy",
                      "Data Interpretation"],
            "Essay": ["Essay Writing Practice on Contemporary Themes"],
            "Optional Subject": ["Add topics in EXAM_CONFIG"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs", "Answer-Writing"],
        full_mock_questions=100,
        pattern_note="Prelims: GS Paper I (100 Qs, 200 marks, 2 hrs, -1/3 negative) + CSAT Paper II (80 Qs, 200 marks, qualifying, 2 hrs). Mains: 9 descriptive papers including Essay, GS I-IV, Optional I-II, and qualifying language papers. Verify exact details from the latest UPSC notification.",
    ),
    "SSC": blueprint(
        "SSC", "Staff Selection Commission",
        ["Quantitative Aptitude", "General Intelligence and Reasoning", "English Language", "General Awareness"],
        ["Hindi", "English"], "English",
        {
            "Quantitative Aptitude": ["Number System", "Percentage", "Ratio and Proportion", "Average",
                                       "Profit, Loss and Discount", "Simple and Compound Interest", "Time, Speed and Distance",
                                       "Time and Work", "Algebra", "Geometry", "Trigonometry", "Mensuration",
                                       "Data Interpretation", "Statistics"],
            "General Intelligence and Reasoning": ["Analogy", "Classification", "Series", "Coding-Decoding",
                                                     "Blood Relations", "Direction Sense", "Syllogism",
                                                     "Non-Verbal Reasoning", "Puzzle and Seating Arrangement",
                                                     "Statement and Conclusion"],
            "English Language": ["Grammar", "Vocabulary", "Reading Comprehension", "Cloze Test",
                                  "Spotting Errors", "Sentence Improvement", "Para Jumbles"],
            "General Awareness": ["Indian History", "Indian and World Geography", "Indian Polity", "Indian Economy",
                                   "General Science", "Static GK", "Current Affairs"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        full_mock_questions=100,
        pattern_note="Tier-wise structure varies by post (CGL/CHSL/MTS etc.) — Tier 1 is commonly 100 objective questions in 60 minutes. Verify the exact tier structure and marking for the specific SSC exam you're targeting.",
    ),
    "Railway / RRB": blueprint(
        "Railway / RRB", "Railway Recruitment Boards",
        ["Mathematics", "General Intelligence and Reasoning", "General Science", "General Awareness and Current Affairs"],
        ["Hindi", "English"], "Hindi",
        {
            "Mathematics": ["Number System", "Percentage", "Ratio and Proportion", "Time, Work and Distance",
                             "Simple and Compound Interest", "Profit and Loss", "Mensuration", "Algebra",
                             "Geometry and Trigonometry", "Statistics and Data Interpretation"],
            "General Intelligence and Reasoning": ["Analogies", "Number and Alphabet Series", "Coding-Decoding",
                                                     "Puzzle", "Data Sufficiency", "Statement-Conclusion",
                                                     "Blood Relations", "Direction Sense"],
            "General Science": ["Physics Basics", "Chemistry Basics", "Biology Basics (up to 10th standard level)"],
            "General Awareness and Current Affairs": ["Indian History", "Indian Geography", "Indian Polity",
                                                        "Indian Economy", "Sports", "Culture", "Current Affairs"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        full_mock_questions=100,
        pattern_note="Varies by post (NTPC/Group D/ALP) — commonly 100 objective questions per CBT stage. Verify exact question count/duration/marking for the specific RRB exam you're targeting.",
    ),
    "Banking": blueprint(
        "Banking", "IBPS / SBI / RBI (varies by exam)",
        ["Quantitative Aptitude", "Reasoning Ability", "English Language", "General/Banking Awareness", "Computer Knowledge"],
        ["Hindi", "English"], "English",
        {
            "Quantitative Aptitude": ["Number Series", "Simplification and Approximation", "Data Interpretation",
                                       "Quadratic Equations", "Percentage, Ratio and Average", "Profit and Loss",
                                       "Simple and Compound Interest", "Time, Speed and Distance", "Time and Work"],
            "Reasoning Ability": ["Puzzle and Seating Arrangement", "Syllogism", "Inequality", "Coding-Decoding",
                                   "Blood Relations", "Direction Sense", "Alphanumeric Series", "Logical Reasoning"],
            "English Language": ["Reading Comprehension", "Cloze Test", "Error Spotting", "Sentence Improvement",
                                  "Para Jumbles", "Fillers", "Vocabulary"],
            "General/Banking Awareness": ["Banking Terms", "RBI and Monetary Policy", "Financial Institutions",
                                           "Government Schemes", "Current Affairs", "Static GK"],
            "Computer Knowledge": ["Computer Fundamentals", "MS Office", "Internet and Networking", "Banking Software Basics"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        full_mock_questions=100,
        pattern_note="Prelims commonly 100 sectional questions in 60 minutes (varies by exam — PO/Clerk/SO); Mains adds sections and duration. Verify against the specific bank exam's official notification.",
    ),
    "Talati": blueprint(
        "Talati", "Gujarat Panchayat Service Selection Board",
        ["Gujarati Language", "General Knowledge", "Mathematics and Reasoning", "Computer Awareness",
         "Panchayati Raj and Rural Development"],
        ["Gujarati"], "Gujarati",
        {
            "Gujarati Language": ["Grammar", "Vocabulary", "Comprehension", "Idioms and Proverbs"],
            "General Knowledge": ["History of Gujarat and India", "Geography of Gujarat and India", "Indian Constitution",
                                   "Current Affairs", "General Science", "Sports and Culture"],
            "Mathematics and Reasoning": ["Number System", "Percentage", "Ratio and Proportion", "Simple and Compound Interest",
                                           "Time and Work", "Averages", "Logical Reasoning", "Series and Coding"],
            "Computer Awareness": ["Computer Fundamentals", "MS Office", "Internet Basics", "E-Governance"],
            "Panchayati Raj and Rural Development": ["Panchayati Raj Structure in Gujarat", "Rural Development Schemes",
                                                       "Role and Duties of a Talati-cum-Mantri"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        pattern_note="Objective MCQ single paper — verify current question count, marks, duration and negative marking from the latest recruitment advertisement.",
    ),
    "GSSSB": blueprint(
        "GSSSB", "Gujarat Subordinate Service Selection Board",
        ["Gujarati Language", "General Knowledge", "Mathematics and Reasoning", "Computer Awareness", "Current Affairs"],
        ["Gujarati", "English"], "Gujarati",
        {
            "Gujarati Language": ["Grammar", "Vocabulary", "Comprehension"],
            "General Knowledge": ["History and Culture of Gujarat and India", "Geography of Gujarat and India",
                                   "Indian Polity and Constitution", "Indian Economy", "General Science"],
            "Mathematics and Reasoning": ["Arithmetic", "Percentage and Averages", "Time and Work",
                                           "Logical Reasoning", "Data Interpretation"],
            "Computer Awareness": ["Computer Fundamentals", "MS Office", "Internet Basics"],
            "Current Affairs": ["National Current Affairs", "Gujarat Current Affairs", "International Current Affairs"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        pattern_note="Pattern varies by the specific post/advertisement GSSSB is recruiting for — verify question count, marks and duration from that advertisement.",
    ),
    "Gujarat Police Constable": blueprint(
        "Gujarat Police Constable", "Gujarat Police Recruitment Board / LRB",
        ["Gujarati Language", "General Knowledge", "Current Affairs", "Reasoning", "Basic Mathematics"],
        ["Gujarati"], "Gujarati",
        {
            "Gujarati Language": ["Grammar", "Vocabulary", "Comprehension"],
            "General Knowledge": ["History of Gujarat and India", "Geography of Gujarat and India",
                                   "Indian Constitution and Polity", "General Science"],
            "Current Affairs": ["National Current Affairs", "Gujarat Current Affairs", "Sports"],
            "Reasoning": ["Analogy", "Series", "Coding-Decoding", "Blood Relations", "Direction Sense"],
            "Basic Mathematics": ["Number System", "Percentage", "Ratio and Proportion", "Time and Work", "Averages"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        pattern_note="Written exam is followed by PST/PET (physical tests) which are non-written and outside this platform's scope. Verify current written-exam question count/marks/duration from the latest LRB advertisement.",
    ),
    "TET-1": blueprint(
        "TET-1", "Gujarat State Examination Board (Std. 1-5 teachers)",
        ["Child Development and Pedagogy", "Language I (Gujarati)", "Language II (English/Hindi)",
         "Mathematics", "Environmental Studies"],
        ["Gujarati", "English"], "Gujarati",
        {
            "Child Development and Pedagogy": ["Child Development Concepts", "Learning and Pedagogy",
                                                 "Inclusive Education", "Assessment for Learning"],
            "Language I (Gujarati)": ["Language Comprehension", "Pedagogy of Language Development", "Grammar"],
            "Language II (English/Hindi)": ["Language Comprehension", "Pedagogy of Language Development", "Grammar"],
            "Mathematics": ["Number Concepts", "Geometry", "Measurement", "Pedagogical Issues in Teaching Maths"],
            "Environmental Studies": ["Family and Friends", "Food", "Shelter", "Water", "Travel", "Pedagogical Issues in EVS"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Objective MCQ paper (commonly 150 questions, 150 minutes, in past cycles) — verify the current question count/duration/marking from the latest GSEB TET notification.",
    ),
    "TET-2": blueprint(
        "TET-2", "Gujarat State Examination Board (Std. 6-8 teachers)",
        ["Child Development and Pedagogy", "Language I (Gujarati)", "Language II (English/Hindi)",
         "Mathematics and Science (or) Social Science"],
        ["Gujarati", "English"], "Gujarati",
        {
            "Child Development and Pedagogy": ["Child Development Concepts", "Learning and Pedagogy",
                                                 "Inclusive Education", "Assessment for Learning"],
            "Language I (Gujarati)": ["Language Comprehension", "Pedagogy of Language Development", "Grammar"],
            "Language II (English/Hindi)": ["Language Comprehension", "Pedagogy of Language Development", "Grammar"],
            "Mathematics and Science (or) Social Science": [
                "Mathematics: Number System, Algebra, Geometry, Mensuration, Pedagogy of Maths",
                "Science: Physics, Chemistry, Biology Basics, Pedagogy of Science",
                "Social Science: History, Geography, Civics, Economics, Pedagogy of Social Science",
            ],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Objective MCQ paper; candidate chooses Maths-Science OR Social Science paper based on subject. Verify current question count/duration/marking from the latest GSEB TET notification.",
    ),
    "TAT": blueprint(
        "TAT", "Gujarat Secondary Education Board (Secondary teachers)",
        ["General Knowledge and Current Affairs", "Teaching Aptitude and Pedagogy", "Subject Knowledge"],
        ["Gujarati", "English"], "Gujarati",
        {
            "General Knowledge and Current Affairs": ["History and Geography of Gujarat and India",
                                                        "Indian Constitution", "Current Affairs", "General Science"],
            "Teaching Aptitude and Pedagogy": ["Educational Psychology", "Teaching Methods", "Classroom Management",
                                                "Assessment and Evaluation"],
            "Subject Knowledge": ["Add topics in EXAM_CONFIG"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        pattern_note="Objective MCQ paper; exact composition depends on chosen subject stream — verify current question count/duration/marking from the latest TAT notification.",
    ),
    "HTAT": blueprint(
        "HTAT", "Gujarat Secondary Education Board (Head Teacher aptitude)",
        ["Educational Administration and Management", "School Leadership", "Gujarat Education Policy",
         "General Knowledge and Reasoning", "Gujarati Language"],
        ["Gujarati", "English"], "Gujarati",
        {
            "Educational Administration and Management": ["Office and Financial Management", "Educational Rules and Regulations"],
            "School Leadership": ["Instructional Leadership", "Staff Management", "Community Participation"],
            "Gujarat Education Policy": ["RTE Act", "Gunotsav", "Mid-Day Meal Scheme", "Government Education Schemes"],
            "General Knowledge and Reasoning": ["Current Affairs", "General Science", "Logical Reasoning"],
            "Gujarati Language": ["Grammar", "Comprehension"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Objective MCQ paper for aspiring Head Teachers — verify current question count/duration/marking from the latest HTAT notification.",
    ),
    "CA": blueprint(
        "CA", "Institute of Chartered Accountants of India (ICAI)",
        ["Foundation", "Intermediate Group 1", "Intermediate Group 2", "Final Group 1", "Final Group 2"],
        ["English"], "English",
        {
            "Foundation": ["Accounting", "Business Laws", "Quantitative Aptitude", "Business Economics"],
            "Intermediate Group 1": ["Advanced Accounting", "Corporate and Other Laws", "Taxation (Direct + Indirect)"],
            "Intermediate Group 2": ["Cost and Management Accounting", "Auditing and Ethics", "Financial and Strategic Management"],
            "Final Group 1": ["Financial Reporting", "Advanced Financial Management", "Advanced Auditing and Professional Ethics"],
            "Final Group 2": ["Direct Tax Laws and International Taxation", "Indirect Tax Laws", "Integrated Business Solutions"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock", "Flashcards"],
        pattern_note="Paper-wise structure with objective + descriptive sections varies by level (Foundation/Inter/Final) and has changed under the new ICAI scheme — verify current paper-wise marks/pattern from the latest ICAI study material and notification.",
    ),
    "CS": blueprint(
        "CS", "Institute of Company Secretaries of India (ICSI)",
        ["Foundation", "Executive Group 1", "Executive Group 2", "Professional Group 1", "Professional Group 2", "Professional Group 3"],
        ["English"], "English",
        {
            "Foundation": ["Business Environment and Law", "Business Management, Ethics and Entrepreneurship",
                           "Business Economics", "Fundamentals of Accounting and Auditing"],
            "Executive Group 1": ["Jurisprudence, Interpretation and General Laws", "Company Law and Practice",
                                   "Setting up of Business, Industrial and Labour Laws"],
            "Executive Group 2": ["Corporate Accounting and Financial Management", "Capital Market and Securities Laws",
                                   "Economic, Business and Commercial Laws", "Tax Laws and Practice"],
            "Professional Group 1": ["Environmental, Social and Governance Principles and Practice",
                                      "Drafting, Pleadings and Appearances", "Corporate Restructuring, Insolvency, Liquidation and Winding-up"],
            "Professional Group 2": ["Corporate Funding and Listing in Stock Exchanges", "Multidisciplinary Case Studies"],
            "Professional Group 3": ["Governance, Risk Management, Compliances and Ethics", "Advanced Tax Laws and Practice"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Foundation is objective MCQ; Executive and Professional are largely descriptive — the exact paper list/marks have changed under ICSI's new syllabus, verify against the latest ICSI notification.",
    ),
    "CMA": blueprint(
        "CMA", "Institute of Cost Accountants of India (ICMAI)",
        ["Foundation", "Intermediate Group 1", "Intermediate Group 2", "Final Group 3", "Final Group 4"],
        ["English"], "English",
        {
            "Foundation": ["Fundamentals of Business Laws and Business Communication", "Fundamentals of Financial and Cost Accounting",
                           "Fundamentals of Business Mathematics and Statistics", "Fundamentals of Business Economics and Management"],
            "Intermediate Group 1": ["Business Laws and Ethics", "Financial Accounting", "Direct and Indirect Taxation",
                                      "Cost Accounting"],
            "Intermediate Group 2": ["Operations Management and Strategic Management", "Corporate Accounting and Auditing",
                                      "Financial Management and Business Data Analytics", "Management Accounting"],
            "Final Group 3": ["Corporate and Economic Laws", "Strategic Financial Management", "Direct Tax Laws and International Taxation",
                               "Strategic Cost Management"],
            "Final Group 4": ["Cost and Management Audit", "Corporate Financial Reporting", "Indirect Tax Laws and Practice",
                               "Strategic Performance Management and Business Valuation"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="Paper-wise structure with objective + descriptive sections — verify current paper-wise marks/pattern from the latest ICMAI study material and notification.",
    ),
    "Gujarat Forest Guard": blueprint(
        "Gujarat Forest Guard (Vanrakshak / Vanpal)", "Gujarat Forest Department (Van Vibhag)",
        ["Environment & Forest", "General Knowledge", "General Mathematics", "Gujarati Language & Grammar"],
        ["Gujarati"], "Gujarati",
        {
            "Environment & Forest": [
                "Forest Cover of Gujarat", "National Parks and Wildlife Sanctuaries of Gujarat",
                "Wildlife Protection Act and Biodiversity", "Medicinal Plants of Gujarat",
                "Pollution and Climate Change", "Agro-forestry and Social Forestry",
            ],
            "General Knowledge": [
                "History of Gujarat", "Geography of Gujarat", "Indian Constitution and Polity",
                "General Science", "Sports and Awards", "Government Schemes of Gujarat",
            ],
            "General Mathematics": [
                "Arithmetic", "Number Series", "Simplification and Approximation",
                "Percentage and Ratio", "Time Speed and Distance", "Simple and Compound Interest",
            ],
            "Gujarati Language & Grammar": [
                "Gujarati Vyakaran", "Samanarthi and Viruddharthi", "Comprehension", "Vocabulary",
            ],
        },
        ["Notes", "Quick-Revision", "Practice", "Topic-Test", "Chapter-Test", "Subject-Test", "Full-Mock", "Current-Affairs"],
        pattern_note="Objective exam approx 200 Marks / 100 Questions: Environment & Forest about 50%, General Knowledge 25%, General Mathematics 12.5%, Gujarati Language 12.5%. Verify the exact split and marking from the current Forest Department notification.",
    ),
    "NDA & CDS": blueprint(
        "NDA & CDS (UPSC Defence Services)", "Union Public Service Commission",
        ["Mathematics", "General Knowledge", "English"], ["English", "Hindi"], "English",
        {
            "Mathematics": [
                "Algebra", "Matrices and Determinants", "Trigonometry", "Analytical Geometry (2D and 3D)",
                "Differential Calculus", "Integral Calculus", "Vector Algebra", "Statistics and Probability",
            ],
            "General Knowledge": [
                "Physics", "Chemistry", "General Science", "Geography of India and the World",
                "History and Social Studies", "Defence and International Affairs",
            ],
            "English": ["Grammar", "Vocabulary", "Reading Comprehension", "Spotting Errors"],
        },
        ["Notes", "Quick-Revision", "PYQ", "Practice", "Topic-Test", "Chapter-Test", "Subject-Test", "Full-Mock"],
        pattern_note="NDA: Mathematics (300 marks) + General Ability Test 600 marks (English 200 + General Knowledge 400), then SSB interview. CDS: separate English / General Knowledge / Elementary Mathematics papers per academy. Verify the exact current pattern from the latest UPSC notification.",
    ),
}


# ============================================================================ #
# ENGINE CORE — config-driven resource matrix, syllabus registry, resource
# planner, HTML/content validation, build manifests, auto-repair and audit.
#
# The generation loop, DB and Telegram handlers live further down. This section
# is the *engine brain*: it decides WHAT must be built for every exam (and at
# which level), how each finished file is validated, whether an exam may
# truthfully be reported COMPLETE, and what to rebuild when a check fails.
#
# Everything here is configuration-driven and exam-agnostic — a new exam added
# to EXAM_CONFIG is picked up automatically by AUTO BUILD ALL.
# ============================================================================ #

import collections  # noqa: E402  (placed with the engine, after EXAM_CONFIG)

# ---------------------------------------------------------------------------
# BUILD_CONFIG / VALIDATION_CONFIG — one place for scale, retry and validation
# knobs. No hard-coded values are scattered through the engine.
# ---------------------------------------------------------------------------
BUILD_CONFIG: dict[str, Any] = {
    "max_concurrent_generations": MAX_WORKERS,       # asyncio workers = parallel AI calls
    "max_retries_transient": MAX_AI_RETRIES,         # bounded retries for API/timeout/rate-limit errors
    "max_repairs_content": 2,                        # extra passes for content that fails validation
    "request_timeout_seconds": HTTP_TIMEOUT_SECONDS,
    "batch_size": 200,                               # jobs inserted per DB batch chunk
    "min_main_chars": 240,                           # below this an HTML <main> is "insufficient content"
    "syllabus_hub": HUB_FILENAME,
}

VALIDATION_CONFIG: dict[str, Any] = {
    "reject_empty_files": True,
    "require_full_html": True,       # doctype/html/head/body structure
    "require_title": True,
    "require_main_min_chars": BUILD_CONFIG["min_main_chars"],
    "quiz_data_present": True,       # question resources must embed the quiz player payload
    "internal_links_resolve": True,  # hub/link audit checks local href targets exist
}

# ---------------------------------------------------------------------------
# RESOURCE_SCOPE — the hierarchy level each resource type belongs to.
#   "unit"    -> one file per syllabus line-item (chapter/topic as listed)
#   "chapter" -> one file per listed chapter (the stored unit IS a chapter)
#   "subject" -> one file per subject, spanning every chapter of it
#   "exam"    -> one file per exam, spanning the whole syllabus
#   "special" -> never auto-duplicated into static topics (e.g. Current Affairs)
#
# Full-Mock / Full-Syllabus-Mock / Revision-Test belong to the EXAM level — they
# are NEVER duplicated into every topic. Subject-Test belongs to the SUBJECT
# level. This is the resource-dependency rule that stops duplication.
# ---------------------------------------------------------------------------
RESOURCE_SCOPE: dict[str, str] = {
    # Unit (topic/chapter-line) level — deep study + practice per line item
    "Notes": "unit", "Quick-Revision": "unit", "Formula-Sheet": "unit",
    "Mind-Map": "unit", "Important-Facts": "unit", "Shortcuts": "unit",
    "Solved-Examples": "unit", "Practice": "unit", "PYQ": "unit",
    "Topic-Test": "unit", "Flashcards": "unit", "Common-Mistakes": "unit",
    "Concept-Revision": "unit",
    # Chapter level — the stored unit is a chapter, so these are one per unit
    "Chapter-Notes": "chapter", "Chapter-Revision": "chapter",
    "Chapter-Question-Bank": "chapter", "Chapter-Test": "chapter",
    "Chapter-Mistake-Test": "chapter", "Chapter-Revision-Test": "chapter",
    # Subject level — one file per subject
    "Subject-Notes": "subject", "Subject-Revision": "subject",
    "Subject-Question-Bank": "subject", "Subject-PYQ": "subject",
    "Subject-Test": "subject", "Subject-Revision-Test": "subject",
    "Subject-Mixed-Practice": "subject",
    # Exam level — one file per exam
    "Full-Syllabus-Notes": "exam", "Full-Syllabus-Revision": "exam",
    "Complete-PYQ-Collection": "exam", "PYQ-Analysis": "exam",
    "Mixed-Practice": "exam", "Full-Mock": "exam", "Grand-Mock": "exam",
    "Revision-Test": "exam", "Mistake-Test": "exam", "Important-Topics": "exam",
    "Expected-Concepts": "exam", "Last-Minute-Revision": "exam",
    "Exam-Strategy": "exam", "Exam-Pattern-Guide": "exam",
    "Time-Management": "exam", "Full-Syllabus-Mock": "exam", "Daily-Test": "exam",
    # Current affairs — scoped globally, never cloned into every static topic
    "Current-Affairs": "special",
}

# Advisory study path per level. The engine keeps resources that are listed for
# an exam AND supported by a builder; within each level they are produced in
# this dependency order (Notes before Practice, tests after study material).
RESOURCE_DEPENDENCIES: dict[str, list[str]] = {
    "unit": ["Notes", "Quick-Revision", "Formula-Sheet", "Mind-Map", "Flashcards",
             "Solved-Examples", "Shortcuts", "Important-Facts", "Common-Mistakes",
             "Concept-Revision", "Practice", "PYQ", "Topic-Test"],
    "chapter": ["Chapter-Notes", "Chapter-Revision", "Chapter-Question-Bank",
                "Chapter-Test", "Chapter-Mistake-Test", "Chapter-Revision-Test"],
    "subject": ["Subject-Notes", "Subject-Revision", "Subject-Question-Bank",
                "Subject-PYQ", "Subject-Mixed-Practice", "Subject-Test",
                "Subject-Revision-Test"],
    "exam": ["Full-Syllabus-Notes", "Full-Syllabus-Revision", "Important-Topics",
             "Expected-Concepts", "Exam-Pattern-Guide", "Last-Minute-Revision",
             "Exam-Strategy", "Time-Management", "Mixed-Practice",
             "Complete-PYQ-Collection", "PYQ-Analysis", "Full-Syllabus-Mock",
             "Full-Mock", "Grand-Mock", "Mistake-Test", "Revision-Test"],
}

def resource_catalog() -> dict[str, dict[str, Any]]:
    """Catalog entries (alias -> label/scope). Built lazily because resource_label
    is declared further down the file — the engine only calls this at runtime."""
    names: set[str] = set(RESOURCE_SCOPE)
    for level_resources in RESOURCE_DEPENDENCIES.values():
        names.update(level_resources)
    return {
        name: {"label": resource_label(name), "scope": RESOURCE_SCOPE.get(name, "unit")}  # noqa: F821
        for name in sorted(names)
    }

# ---------------------------------------------------------------------------
# SYLLABUS REGISTRY — exam metadata separate from the editable topic lists.
# The registry NEVER invents official facts: any field Prakash has not filled in
# SYLLABUS_META below stays VERIFY_REQUIRED (or None) and is never presented as
# official in the UI or in generated HTML.
# ---------------------------------------------------------------------------

# EDIT-ME: fill verified official syllabus details here. Only what you enter here
# is ever presented as "official" — everything else is reported VERIFY_REQUIRED.
SYLLABUS_META: dict[str, dict[str, Any]] = {
    # "NEET": {
    #     "official_syllabus": "https://...", "official_notification": "https://...",
    #     "official_syllabus_pdf": "https://...", "trusted_secondary": "https://...",
    #     "applicable_year": "2026", "last_verified": "2026-09-08", "posts": [],
    # },
}


def _registry_from_exam(exam: str, cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "exam": cfg.get("exam_name", exam),
        "authority": cfg.get("authority") or VERIFY_REQUIRED,
        "post": VERIFY_REQUIRED,
        "applicable_year": VERIFY_REQUIRED,
        "official_syllabus": None,
        "official_notification": None,
        "official_syllabus_pdf": None,
        "trusted_secondary": None,
        "source_type": "AI inference" if cfg.get("exam_pattern") == VERIFY_REQUIRED else "editor-verified config",
        "syllabus_status": VERIFY_REQUIRED,
        "last_verified": None,
        "post_specific": bool(cfg.get("posts")),
        "subjects": list(cfg.get("subjects") or []),
        "chapters_total": sum(
            1 for units in (cfg.get("topics") or {}).values()
            for unit in units if unit != "Add topics in EXAM_CONFIG"
        ),
        "units_total": sum(
            len([unit for unit in units if unit != "Add topics in EXAM_CONFIG"])
            for units in (cfg.get("topics") or {}).values()
        ),
    }


def build_syllabus_registry() -> dict[str, dict[str, Any]]:
    """Build the live registry from EXAM_CONFIG + SYLLABUS_META. Called once at
    import; AUTO BUILD ALL re-reads it every run so new exams appear instantly."""
    registry: dict[str, dict[str, Any]] = {}
    for exam, cfg in EXAM_CONFIG.items():
        entry = _registry_from_exam(exam, cfg)
        entry.update(SYLLABUS_META.get(exam, {}))
        # source_type is derived, never overridable to a lie
        if entry.get("official_syllabus") or entry.get("official_notification"):
            entry["source_type"] = "official (editor-entered)"
            entry["syllabus_status"] = "VERIFIED_AS_ENTERED"
        else:
            entry["source_type"] = "AI inference — VERIFY_REQUIRED"
            entry["syllabus_status"] = VERIFY_REQUIRED
        registry[exam] = entry
    return registry


SYLLABUS_REGISTRY: dict[str, dict[str, Any]] = build_syllabus_registry()


def registry_entry(exam: str) -> dict[str, Any]:
    return SYLLABUS_REGISTRY.get(exam) or _registry_from_exam(exam, EXAM_CONFIG.get(exam, {}))


def resource_supported(resource_type: str) -> bool:
    """A resource can only be queued if a real builder/schema exists for it.
    (REFERENCES the resource-type sets declared further down — resolved at
    call time, so order in the file does not matter.)"""
    if resource_type in {"Notes", "Quick-Revision", "Formula-Sheet", "Flashcards", "Answer-Writing"}:
        return True
    return resource_type in QUESTION_RESOURCE_TYPES  # noqa: F821 (defined later)


def resource_scope_of(resource_type: str) -> str:
    return RESOURCE_SCOPE.get(resource_type, "unit")


def stable_job_key(exam: str, language: str, subject: str, topic: str, resource_type: str) -> str:
    """Stable identity used to rerun only missing resources without duplication."""
    raw = "|".join((exam, language, subject, topic, resource_type)).casefold()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def missing_plan_jobs(exam: str, language: Optional[str] = None, resources: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Return only planned resources whose validated HTML file is absent."""
    missing: list[dict[str, Any]] = []
    for job in plan_exam_build(exam, language=language, resources=resources):
        path = Path(OUTPUT_DIR) / expected_resource_rel(exam, job["subject"], job["topic"], job["resource_type"])
        if not path.exists() or validate_html_resource(path.read_text(encoding="utf-8", errors="replace"), job["resource_type"]):
            missing.append(job)
    return missing


# ---------------------------------------------------------------------------
# RESOURCE PLANNER — builds the full required-job plan for an exam:
# EXAM -> SUBJECT -> CHAPTER -> RESOURCE, then flattens into one job per file
# with the correct level scope. This is what AUTO BUILD ALL feeds the queue.
# ---------------------------------------------------------------------------
def plan_exam_build(
    exam: str,
    language: Optional[str] = None,
    resources: Optional[list[str]] = None,
    subject_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return the ordered list of jobs needed to fully build `exam`. Each job is
    a dict with subject/topic/chapter/resource_type/question_count. A job is only
    produced for resources that actually have a builder (resource_supported)."""
    blueprint_data = EXAM_CONFIG[exam]
    language = language or blueprint_data.get("recommended_language") or "English"
    pool = list(resources) if resources else list(blueprint_data.get("recommended_resources") or [])
    pool = [r for r in pool if resource_supported(r)]

    unit_res = [r for r in pool if resource_scope_of(r) in ("unit", "chapter")]
    subject_res = [r for r in pool if resource_scope_of(r) == "subject"]
    exam_res = [r for r in pool if resource_scope_of(r) == "exam"]
    special_res = [r for r in pool if resource_scope_of(r) == "special"]

    def order(level: str, chosen: list[str]) -> list[str]:
        ranked = RESOURCE_DEPENDENCIES.get(level, [])
        return sorted(chosen, key=lambda r: (ranked.index(r) if r in ranked else 999, r))

    jobs: list[dict[str, Any]] = []
    topics_map = blueprint_data.get("topics") or {}
    for subject, units in topics_map.items():
        if subject_filter and subject.casefold() != str(subject_filter).casefold():
            continue
        units = [u for u in units if u != "Add topics in EXAM_CONFIG"]
        # Unit-level + chapter-level files: one per listed chapter line item
        for unit in units:
            for resource in order("unit", unit_res):
                jobs.append({
                    "job_key": stable_job_key(exam, language, subject, unit, resource),
                    "subject": subject, "topic": unit, "chapter": unit,
                    "resource_type": resource,
                    "question_count": resolve_question_count(exam, resource, None),  # noqa: F821
                })
        # Subject-level files: one per subject, spanning all its chapters
        for resource in order("subject", subject_res):
            jobs.append({
                "subject": subject,
                "topic": f"Complete {subject} Syllabus",
                "chapter": f"Entire {subject}",
                "resource_type": resource,
                "question_count": resolve_question_count(exam, resource, None),  # noqa: F821
            })
    for job in jobs:
        job.setdefault("job_key", stable_job_key(exam, language, job["subject"], job["topic"], job["resource_type"]))
    # Exam-level files: exactly one per exam, spanning every subject
    exam_bucket = "Full-Syllabus"
    for resource in order("exam", exam_res):
        jobs.append({
            "subject": exam_bucket,
            "topic": f"{exam} Complete Syllabus",
            "chapter": f"Entire {exam} syllabus",
            "resource_type": resource,
            "question_count": resolve_question_count(exam, resource, None),  # noqa: F821
        })
    for resource in special_res:
        jobs.append({
            "subject": exam_bucket,
            "topic": f"{exam} {resource_label(resource)}",
            "chapter": f"Entire {exam} syllabus",
            "resource_type": resource,
            "question_count": resolve_question_count(exam, resource, None),  # noqa: F821
        })
    for job in jobs:
        job["job_key"] = stable_job_key(exam, language, job["subject"], job["topic"], job["resource_type"])
    return jobs


def plan_summary(exam: str, language: Optional[str] = None) -> dict[str, Any]:
    """Machine-readable plan summary used by the manifest and the dashboard."""
    jobs = plan_exam_build(exam, language=language)
    registry = registry_entry(exam)
    scope_counter: "collections.Counter[str]" = collections.Counter(
        resource_scope_of(j["resource_type"]) for j in jobs
    )
    per_subject: dict[str, int] = collections.Counter(j["subject"] for j in jobs)
    return {
        "exam": exam,
        "registry": registry,
        "language": language or (EXAM_CONFIG[exam].get("recommended_language") or "English"),
        "subjects_total": len(EXAM_CONFIG[exam].get("subjects") or []),
        "units_total": registry.get("units_total", 0),
        "resources_required": len(jobs),
        "jobs_by_scope": dict(scope_counter),
        "jobs_by_subject": dict(per_subject),
    }


def expected_resource_rel(exam: str, subject: str, topic: str, resource_type: str) -> Path:
    """Mirror the exact path the worker writes, so the manifest can check whether
    a required file truly exists without guessing."""
    label = safe_filename(resource_label(resource_type))  # noqa: F821
    return Path(safe_filename(exam)) / safe_filename(subject) / label / f"{safe_filename(topic)}-{label}.html"


# ---------------------------------------------------------------------------
# VALIDATION — content/data-level checks already live in validate_content();
# these are the *output* checks that run on every finished HTML file.
# ---------------------------------------------------------------------------
def strip_markup(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def validate_html_resource(text: str, resource_type: str) -> list[str]:
    """Return a list of problems with a generated HTML file. Empty list == valid."""
    problems: list[str] = []
    if not text or not text.strip():
        return ["empty file"]
    low = text.lower()
    if VALIDATION_CONFIG["require_full_html"]:
        for token in ("<!doctype html", "<html", "<head", "<body", "</html>"):
            if token not in low:
                problems.append(f"missing {token}")
    if VALIDATION_CONFIG["require_title"] and ("<title>" not in low or "</title>" not in low):
        problems.append("missing <title>")
    main_match = re.search(r"(?is)<main>(.*?)</main>", text)
    body_match = re.search(r"(?is)<body>(.*?)</body>", text)
    main_text = strip_markup(main_match.group(1) if main_match else (body_match.group(1) if body_match else text))
    if len(main_text) < int(VALIDATION_CONFIG["require_main_min_chars"]):
        problems.append(f"main content too thin ({len(main_text)} chars)")
    if resource_type in QUESTION_RESOURCE_TYPES and VALIDATION_CONFIG["quiz_data_present"]:  # noqa: F821
        if "const questions=" not in text:
            problems.append("quiz data missing")
    return problems


def broken_links_in_file(path: Path) -> list[str]:
    """Scan one HTML file for local (non-http/#/mailto) href targets that do not
    resolve on disk. Used by the link audit on hubs and resource pages."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"unreadable: {exc}"]
    broken: list[str] = []
    base = path.parent
    for href in re.findall(r"""href\s*=\s*["']([^"'#]+)["']""", text, flags=re.I):
        if href.startswith(("http://", "https://", "mailto:", "tel:", "//", "data:")):
            continue
        target = href.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        if not (base / target).exists():
            broken.append(href)
    return broken


def file_content_digest(path: Path) -> str:
    """Hash of the visible <main> text — used for duplicate detection across
    files of the same kind (shared foundational passages are allowed only when
    genuinely necessary; identical pages are reported as duplicates)."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    main_match = re.search(r"(?is)<main>(.*?)</main>", text)
    return hashlib.md5(strip_markup(main_match.group(1) if main_match else text).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# MANIFEST + AUDIT — machine-readable state of one exam's library. An exam is
# reported COMPLETE only when every required file exists, passes validation,
# and no broken links / duplicates remain.
# ---------------------------------------------------------------------------
def write_exam_manifest(exam: str, language: Optional[str] = None) -> dict[str, Any]:
    exam_dir = Path(OUTPUT_DIR) / safe_filename(exam)
    exam_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_summary(exam, language=language)
    required_specs = [(j["subject"], j["topic"], j["resource_type"]) for j in plan_exam_build(exam, language=language)]

    existing_paths: set[Path] = set()
    generated = 0
    validated = 0
    failed_files: list[dict[str, Any]] = []
    broken: list[dict[str, str]] = []
    duplicates: list[list[str]] = []
    digest_seen: dict[str, Path] = {}

    for entry in exam_files_flat(exam):  # noqa: F821 (defined later — call time)
        # entry["rel"] is relative to the exam folder, so join onto exam_dir.
        path = exam_dir / entry["rel"]
        existing_paths.add(path.resolve())
        generated += 1
        problems = validate_html_resource(
            path.read_text(encoding="utf-8", errors="replace"), entry["kind"]
        )
        if not problems:
            validated += 1
        else:
            failed_files.append({"file": entry["rel"], "problems": problems})
        broken += [{"file": entry["rel"], "link": link} for link in broken_links_in_file(path)]
        digest = file_content_digest(path)
        if digest:
            previous = digest_seen.get(digest)
            if previous is not None and previous != path:
                duplicates.append([str(previous), str(path)])
            else:
                digest_seen[digest] = path

    missing = [
        {"subject": s, "topic": t, "resource_type": r}
        for s, t, r in required_specs
        if ((Path(OUTPUT_DIR) / expected_resource_rel(exam, s, t, r)).resolve()) not in existing_paths
    ]

    status = "COMPLETE"
    if failed_files or broken or duplicates:
        status = "REVIEW_REQUIRED"
    elif missing:
        status = "INCOMPLETE"

    manifest: dict[str, Any] = {
        "schema": "prepgrid-manifest-1",
        "exam": exam,
        "syllabus_version": registry_entry(exam).get("last_verified") or VERIFY_REQUIRED,
        "source_type": registry_entry(exam).get("source_type"),
        "syllabus_status": registry_entry(exam).get("syllabus_status"),
        "subjects_total": plan["subjects_total"],
        "chapters_total": plan["registry"].get("chapters_total", 0),
        "units_total": plan["units_total"],
        "resources_required": plan["resources_required"],
        "resources_generated": generated,
        "resources_validated": validated,
        "resources_failed": len(failed_files),
        "missing_resources": missing,
        "broken_links": broken,
        "duplicates": duplicates,
        "failed_files": failed_files,
        "status": status,
        "updated_at": now_iso(),  # noqa: F821
    }
    manifest_path = exam_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def audit_all_exams() -> dict[str, Any]:
    """Offline audit over every configured exam. Does NOT generate anything —
    used by VALIDATE/AUDIT ALL and by AUTO BUILD ALL's finishing report."""
    exams: list[str] = []
    reports: dict[str, dict[str, Any]] = {}
    for exam in EXAM_CONFIG:
        manifest = write_exam_manifest(exam)
        reports[exam] = {
            "status": manifest["status"],
            "required": manifest["resources_required"],
            "generated": manifest["resources_generated"],
            "validated": manifest["resources_validated"],
            "failed": manifest["resources_failed"],
            "missing": len(manifest["missing_resources"]),
            "broken": len(manifest["broken_links"]),
            "duplicates": len(manifest["duplicates"]),
        }
        exams.append(exam)
    complete = sum(1 for r in reports.values() if r["status"] == "COMPLETE")
    return {
        "exams_total": len(exams),
        "exams_complete": complete,
        "exams_review": len(exams) - complete,
        "resources_generated": sum(r["generated"] for r in reports.values()),
        "resources_validated": sum(r["validated"] for r in reports.values()),
        "resources_failed": sum(r["failed"] for r in reports.values()),
        "missing_total": sum(r["missing"] for r in reports.values()),
        "broken_total": sum(r["broken"] for r in reports.values()),
        "duplicates_total": sum(r["duplicates"] for r in reports.values()),
        "reports": reports,
        "manifest_paths": [str(Path(OUTPUT_DIR) / safe_filename(e) / "manifest.json") for e in exams],
    }


# ============================================================================ #
# LOGGING AND GENERAL HELPERS
# ============================================================================ #

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sonic-resource-factory")

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
Path(SOURCE_DIR).mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_filename(value: str, fallback: str = "resource") -> str:
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value.strip()).strip("-")
    return value[:100] or fallback


def normalize_question(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9\u0900-\u097f\u0a80-\u0aff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def text_from_message(message: Any) -> str:
    return (message.text or message.caption or "").strip()


def is_placeholder(value: str) -> bool:
    return not value or value.startswith("PASTE_")


def resource_label(value: str) -> str:
    return {
        "Quick-Revision": "Quick Revision",
        "Topic-Test": "Topic Test",
        "Chapter-Test": "Chapter Test",
        "Subject-Test": "Subject Test",
        "Full-Mock": "Full Mock",
        "Daily-Test": "Daily Test",
        "Revision-Test": "Revision Test",
        "Answer-Writing": "Answer Writing",
        "Current-Affairs": "Current Affairs",
    }.get(value, value)


TEST_RESOURCE_TYPES = {
    "Topic-Test",
    "Chapter-Test",
    "Subject-Test",
    "Full-Mock",
    "Full-Syllabus-Mock",
    "Daily-Test",
    "Revision-Test",
}

QUESTION_RESOURCE_TYPES = {
    "Practice",
    "PYQ",
    "Topic-Test",
    "Chapter-Test",
    "Subject-Test",
    "Full-Mock",
    "Full-Syllabus-Mock",
    "Daily-Test",
    "Revision-Test",
    "Current-Affairs",
}


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def progress_bar(done: int, total: int, width: int = 20) -> str:
    ratio = 1.0 if total == 0 else min(1.0, done / total)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_number(text: str, default: int) -> int:
    match = re.search(r"\b(\d{1,5})\b", text)
    return int(match.group(1)) if match else default


def resolve_question_count(exam: str, resource: str, override: Optional[int]) -> Optional[int]:
    """Decide how many questions a job should contain. Notes-style resources
    don't need a count. Full-Mock uses the exam's real official question count
    when it's known (see EXAM_CONFIG[exam]['full_mock_questions']); every
    other test type is floored at MINIMUM_QUIZ_QUESTIONS (30) so no quiz file
    ever comes out thin. An explicit user override (e.g. '/prompt ...
    Questions: 50') always wins and is never floored — an explicit ask is
    respected as-is."""
    if resource in {"Notes", "Quick-Revision", "Flashcards", "Answer-Writing", "Formula-Sheet"}:
        return None
    if override is not None:
        return override
    if resource == "Full-Mock":
        return EXAM_CONFIG.get(exam, {}).get("full_mock_questions") or DEFAULT_QUESTION_COUNT
    if resource == "Full-Syllabus-Mock":
        distribution = EXAM_CONFIG.get(exam, {}).get("subject_distribution")
        if distribution:
            return sum(distribution.values())
        return EXAM_CONFIG.get(exam, {}).get("full_mock_questions") or DEFAULT_QUESTION_COUNT
    if resource == "Chapter-Test":
        return max(CHAPTER_TEST_QUESTIONS, MINIMUM_QUIZ_QUESTIONS)
    if resource == "Subject-Test":
        return max(SUBJECT_TEST_QUESTIONS, MINIMUM_QUIZ_QUESTIONS)
    if resource == "Topic-Test":
        return max(TOPIC_TEST_QUESTIONS, MINIMUM_QUIZ_QUESTIONS)
    return max(DEFAULT_QUESTION_COUNT, MINIMUM_QUIZ_QUESTIONS)


def extract_topics(scope: str, exam: str, subject: Optional[str] = None) -> list[tuple[str, str]]:
    """Resolve a prompt scope into (subject, topic) pairs."""
    blueprint_data = EXAM_CONFIG[exam]
    topics_map = blueprint_data.get("topics", {})
    selected: list[tuple[str, str]] = []
    scope_lower = scope.casefold()
    if "all" in scope_lower or "syllabus" in scope_lower:
        for current_subject, topics in topics_map.items():
            if not subject or current_subject.casefold() == subject.casefold() or current_subject.casefold() in scope_lower:
                selected.extend((current_subject, str(topic)) for topic in topics if topic != "Add topics in EXAM_CONFIG")
    else:
        for line in re.split(r"[,;\n]+", scope):
            line = re.sub(r"^\s*\d+[\s.)-]*", "", line).strip()
            if line:
                selected.append((subject or (blueprint_data["subjects"][0]), line))
    return selected or [(subject or blueprint_data["subjects"][0], "General Topic")]


# ============================================================================ #
# SQLITE PERSISTENCE
# ============================================================================ #


class Database:
    def __init__(self, path: str):
        self.path = path
        self.lock = asyncio.Lock()
        self.conn: Optional[sqlite3.Connection] = None

    async def initialize(self) -> None:
        async with self.lock:
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exam_configs (
                    exam_name TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    exam TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    chapter TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    file_path TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    source_path TEXT,
                    question_count INTEGER,
                    style TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_batch ON jobs(batch_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE TABLE IF NOT EXISTS questions (
                    question_id TEXT PRIMARY KEY,
                    exam TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    chapter TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    normalized_question TEXT NOT NULL,
                    question_hash TEXT NOT NULL UNIQUE,
                    correct_answer TEXT,
                    generation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_questions_scope
                    ON questions(exam, subject, topic, language);
                CREATE TABLE IF NOT EXISTS resources (
                    resource_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    exam TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(exam, subject, topic, resource_type, language)
                );
                CREATE TABLE IF NOT EXISTS builds (
                    batch_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    exams_json TEXT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );
                """
            )
            for exam_name, config in EXAM_CONFIG.items():
                self.conn.execute(
                    "INSERT OR IGNORE INTO exam_configs(exam_name, config_json, updated_at) VALUES (?, ?, ?)",
                    (exam_name, json_text(config), now_iso()),
                )
            self.conn.commit()
            # A crash can leave jobs marked RUNNING. They are safe to resume.
            self.conn.execute(
                "UPDATE jobs SET status='PENDING', error='Recovered after restart' WHERE status='RUNNING'"
            )
            self.conn.commit()

    def _require(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("Database is not initialized")
        return self.conn

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        async with self.lock:
            self._require().execute(query, params)
            self._require().commit()

    async def fetchone(self, query: str, params: tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        async with self.lock:
            return self._require().execute(query, params).fetchone()

    async def fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        async with self.lock:
            return self._require().execute(query, params).fetchall()

    async def add_user(self, user_id: int, added_by: int) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO users(user_id, added_by, created_at) VALUES (?, ?, ?)",
            (user_id, added_by, now_iso()),
        )

    async def remove_user(self, user_id: int) -> None:
        await self.execute("DELETE FROM users WHERE user_id=?", (user_id,))

    async def is_user_allowed(self, user_id: int) -> bool:
        return bool(await self.fetchone("SELECT user_id FROM users WHERE user_id=?", (user_id,)))

    async def add_group(self, chat_id: int, title: str, owner_id: int) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO groups(chat_id, title, owner_id, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, title, owner_id, now_iso()),
        )

    async def remove_group(self, chat_id: int) -> None:
        await self.execute("DELETE FROM groups WHERE chat_id=?", (chat_id,))

    async def is_group_allowed(self, chat_id: int) -> bool:
        return bool(await self.fetchone("SELECT chat_id FROM groups WHERE chat_id=?", (chat_id,)))

    async def add_jobs(self, jobs: list[dict[str, Any]]) -> None:
        if not jobs:
            return
        async with self.lock:
            conn = self._require()
            conn.executemany(
                """
                INSERT INTO jobs(
                    job_id,batch_id,chat_id,owner_id,exam,subject,chapter,topic,
                    resource_type,language,status,attempts,file_path,created_at,
                    source_path,question_count,style
                ) VALUES (
                    :job_id,:batch_id,:chat_id,:owner_id,:exam,:subject,:chapter,:topic,
                    :resource_type,:language,'PENDING',0,NULL,:created_at,
                    :source_path,:question_count,:style
                )
                """,
                jobs,
            )
            conn.commit()

    async def get_job(self, job_id: str) -> Optional[sqlite3.Row]:
        return await self.fetchone("SELECT * FROM jobs WHERE job_id=?", (job_id,))

    async def set_job_running(self, job_id: str) -> None:
        await self.execute("UPDATE jobs SET status='RUNNING', attempts=attempts+1 WHERE job_id=?", (job_id,))

    async def set_job_done(self, job_id: str, path: str) -> None:
        await self.execute(
            "UPDATE jobs SET status='COMPLETED', file_path=?, completed_at=?, error=NULL WHERE job_id=?",
            (path, now_iso(), job_id),
        )

    async def set_job_failed(self, job_id: str, error: str) -> None:
        await self.execute("UPDATE jobs SET status='FAILED', error=? WHERE job_id=?", (error[:2000], job_id))

    async def set_job_pending(self, job_id: str, error: str = "") -> None:
        await self.execute("UPDATE jobs SET status='PENDING', error=? WHERE job_id=?", (error[:2000], job_id))

    async def cancel_pending_for_chat(self, chat_id: int) -> int:
        """Used by /stop and /cancelpending: kill every not-yet-started job for
        this chat at the DATABASE level (not just in-memory), so it can never
        silently resume later — not via /resume, and not via a bot restart."""
        rows = await self.fetchall(
            "SELECT job_id FROM jobs WHERE chat_id=? AND status IN ('PENDING','FAILED')", (chat_id,)
        )
        if rows:
            await self.execute(
                "UPDATE jobs SET status='CANCELLED', error='Cancelled by user' WHERE chat_id=? AND status IN ('PENDING','FAILED')",
                (chat_id,),
            )
        return len(rows)

    async def cancel_all_for_chat(self, chat_id: int) -> int:
        """/reset — clear EVERY non-terminal job for this chat (running, pending,
        retrying, queued, failed) across ALL exams at the DATABASE level. Cancelled
        rows are never picked by a worker, /resume or /retry, so old builds stop
        reappearing and nothing silently comes back after a restart. Terminal rows
        (COMPLETED / already CANCELLED) are kept as history."""
        rows = await self.fetchall(
            "SELECT job_id FROM jobs WHERE chat_id=? AND status NOT IN ('COMPLETED','CANCELLED')", (chat_id,)
        )
        if rows:
            await self.execute(
                "UPDATE jobs SET status='CANCELLED', error='Reset by user' "
                "WHERE chat_id=? AND status NOT IN ('COMPLETED','CANCELLED')",
                (chat_id,),
            )
        return len(rows)

    async def cancel_builds_for_chat(self, chat_id: int) -> int:
        """Mark this chat's still-running engine batches as CANCELLED so they are
        not reported as pending builds."""
        rows = await self.fetchall(
            "SELECT batch_id FROM builds WHERE chat_id=? AND status='RUNNING'", (chat_id,)
        )
        if rows:
            await self.execute(
                "UPDATE builds SET status='CANCELLED', finished_at=? WHERE chat_id=? AND status='RUNNING'",
                (now_iso(), chat_id),
            )
        return len(rows)

    async def batch_jobs(self, batch_id: str) -> list[sqlite3.Row]:
        return await self.fetchall("SELECT * FROM jobs WHERE batch_id=? ORDER BY created_at, job_id", (batch_id,))

    async def pending_jobs(self, chat_id: Optional[int] = None) -> list[sqlite3.Row]:
        if chat_id is None:
            return await self.fetchall("SELECT * FROM jobs WHERE status='PENDING' ORDER BY created_at")
        return await self.fetchall("SELECT * FROM jobs WHERE chat_id=? AND status='PENDING' ORDER BY created_at", (chat_id,))

    async def failed_jobs(self, chat_id: int) -> list[sqlite3.Row]:
        return await self.fetchall("SELECT * FROM jobs WHERE chat_id=? AND status='FAILED' ORDER BY created_at", (chat_id,))

    async def recent_jobs(self, chat_id: int, limit: int = 20) -> list[sqlite3.Row]:
        return await self.fetchall("SELECT * FROM jobs WHERE chat_id=? ORDER BY created_at DESC LIMIT ?", (chat_id, limit))

    async def job_counts(self, batch_id: str) -> dict[str, int]:
        rows = await self.fetchall("SELECT status, COUNT(*) AS count FROM jobs WHERE batch_id=? GROUP BY status", (batch_id,))
        return {row["status"]: int(row["count"]) for row in rows}

    async def existing_resource(self, row: sqlite3.Row) -> Optional[sqlite3.Row]:
        return await self.fetchone(
            """
            SELECT * FROM resources
            WHERE exam=? AND subject=? AND topic=? AND resource_type=? AND language=?
            """,
            (row["exam"], row["subject"], row["topic"], row["resource_type"], row["language"]),
        )

    async def save_resource(self, row: sqlite3.Row, path: str) -> None:
        await self.execute(
            """
            INSERT OR REPLACE INTO resources(
                resource_id,job_id,exam,subject,topic,resource_type,language,file_path,created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                row["job_id"],
                row["exam"],
                row["subject"],
                row["topic"],
                row["resource_type"],
                row["language"],
                path,
                now_iso(),
            ),
        )

    async def question_exists(self, question_hash: str) -> bool:
        return bool(await self.fetchone("SELECT question_id FROM questions WHERE question_hash=?", (question_hash,)))

    async def similar_questions(self, normalized: str, limit: int = 150) -> list[str]:
        rows = await self.fetchall("SELECT normalized_question FROM questions ORDER BY created_at DESC LIMIT ?", (limit,))
        return [str(row["normalized_question"]) for row in rows]

    async def save_question(self, row: sqlite3.Row, question: dict[str, Any], generation_id: str) -> bool:
        normalized = normalize_question(str(question.get("question", "")))
        question_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if not normalized or await self.question_exists(question_hash):
            return False
        async with self.lock:
            try:
                self._require().execute(
                    """
                    INSERT INTO questions(
                        question_id,exam,subject,chapter,topic,resource_type,language,
                        question_text,normalized_question,question_hash,correct_answer,
                        generation_id,created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        row["exam"],
                        row["subject"],
                        row["chapter"],
                        row["topic"],
                        row["resource_type"],
                        row["language"],
                        str(question.get("question", "")),
                        normalized,
                        question_hash,
                        str(question.get("answer", "")),
                        generation_id,
                        now_iso(),
                    ),
                )
                self._require().commit()
                return True
            except sqlite3.IntegrityError:
                return False

    # --- Engine-level persistence (builds) + batch analytics -----------------
    async def add_build(self, batch_id: str, chat_id: int, mode: str, exams: list[str]) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO builds(batch_id, chat_id, mode, exams_json, status, started_at) VALUES (?, ?, ?, ?, 'RUNNING', ?)",
            (batch_id, chat_id, mode, json_text(exams), now_iso()),
        )

    async def finish_build(self, batch_id: str, status: str) -> None:
        await self.execute(
            "UPDATE builds SET status=?, finished_at=? WHERE batch_id=?",
            (status, now_iso(), batch_id),
        )

    async def get_build(self, batch_id: str) -> Optional[sqlite3.Row]:
        return await self.fetchone("SELECT * FROM builds WHERE batch_id=?", (batch_id,))

    async def latest_build(self, chat_id: int) -> Optional[sqlite3.Row]:
        return await self.fetchone(
            "SELECT * FROM builds WHERE chat_id=? ORDER BY started_at DESC LIMIT 1", (chat_id,)
        )

    async def exam_job_counts(self, batch_id: str) -> dict[str, dict[str, int]]:
        rows = await self.fetchall(
            "SELECT exam, status, COUNT(*) AS count FROM jobs WHERE batch_id=? GROUP BY exam, status",
            (batch_id,),
        )
        result: dict[str, dict[str, int]] = {}
        for row in rows:
            result.setdefault(row["exam"], {})[row["status"]] = int(row["count"])
        return result

    async def running_jobs(self, batch_id: str, limit: int = 3) -> list[sqlite3.Row]:
        return await self.fetchall(
            "SELECT exam, subject, topic, resource_type FROM jobs WHERE batch_id=? AND status='RUNNING' ORDER BY created_at LIMIT ?",
            (batch_id, limit),
        )

    async def completed_attempt_counts(self, batch_id: str) -> dict[int, int]:
        """attempts histogram for COMPLETED jobs — attempts>1 means the job was
        auto-repaired/retried at least once before passing (used as the repair
        counter in the final AUTO BUILD report)."""
        rows = await self.fetchall(
            "SELECT attempts FROM jobs WHERE batch_id=? AND status='COMPLETED'", (batch_id,)
        )
        histogram: dict[int, int] = {}
        for row in rows:
            attempts = int(row["attempts"])
            histogram[attempts] = histogram.get(attempts, 0) + 1
        return histogram


# ============================================================================ #
# AI CLIENT
# ============================================================================ #


class AIError(Exception):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class AIClient:
    """Talks to exactly ONE model with ONE API key for every request in the
    batch, so every generated file (notes and quizzes alike) has the same
    style and quality. No key rotation, no model mixing."""

    def __init__(self):
        self.key = AI_API_KEY.strip()
        self.model = AI_MODEL.strip()
        self.cooldown_until = 0.0
        self.lock = asyncio.Lock()
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def _choose_key(self) -> str:
        async with self.lock:
            if not self.key:
                raise AIError("AI credentials are not configured. Edit AI_API_KEY.", retryable=False)
            if self.cooldown_until > time.monotonic():
                raise AIError("The AI key is temporarily rate-limited.", retryable=True)
            return self.key

    async def _cooldown(self, key: str, seconds: float) -> None:
        async with self.lock:
            self.cooldown_until = time.monotonic() + seconds

    async def _choose_model(self) -> str:
        return self.model

    def _endpoint(self) -> str:
        base = AI_BASE_URL.strip().rstrip("/")
        if not base or base.startswith("PASTE_"):
            raise AIError("AI_BASE_URL is not configured.", retryable=False)
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    async def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.35,
        max_tokens: int = 4000,
        timeout_seconds: Optional[float] = None,
    ) -> dict[str, Any]:
        if not self.session:
            raise AIError("AI client is not started.", retryable=False)
        last_error: Optional[AIError] = None
        base_timeout = timeout_seconds or HTTP_TIMEOUT_SECONDS
        request_max_tokens = max_tokens
        call_started = time.monotonic()
        # Hard cap on total wall-clock time for one job's AI call, across all
        # retries. Without this, a job on a slow/unstable connection could
        # keep retrying with an ever-growing timeout for tens of minutes with
        # zero visible output — looking exactly like "bot is stuck, no logs".
        max_total_seconds = 600.0
        for attempt in range(MAX_AI_RETRIES):
            if time.monotonic() - call_started > max_total_seconds:
                logger.warning("AI call giving up after %.0fs total (exceeded %.0fs budget across %s attempts)", time.monotonic() - call_started, max_total_seconds, attempt)
                break
            # The timeout AND the token budget both grow on every retry instead
            # of staying fixed. A fixed budget that repeats identically on every
            # attempt means a response that's genuinely just a little too big
            # for that budget (heavy Notes/Formula-Sheet content in Gujarati,
            # which needs far more tokens per word) gets cut off the exact same
            # way every single time — that's "same topic keeps failing /
            # notes come back incomplete even after retry".
            attempt_timeout = min(480.0, base_timeout * (1.4 ** attempt))
            request_timeout = aiohttp.ClientTimeout(total=attempt_timeout)
            is_last_attempt = attempt == MAX_AI_RETRIES - 1
            key = await self._choose_key()
            model = await self._choose_model()
            logger.info(
                "AI call attempt %s/%s: model=%s timeout=%.0fs max_tokens=%s",
                attempt + 1, MAX_AI_RETRIES, model, attempt_timeout, request_max_tokens,
            )
            payload = {
                "model": model,
                "temperature": temperature,
                "max_tokens": request_max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            try:
                async with self.session.post(
                    self._endpoint(),
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=request_timeout,
                ) as response:
                    body = await response.text()
                    if response.status == 429:
                        await self._cooldown(key, min(90, 5 * (attempt + 1)))
                        raise AIError("AI API rate limit (429).", retryable=True)
                    if response.status in {401, 403}:
                        await self._cooldown(key, 300)
                        raise AIError("AI API rejected a configured key (401/403).", retryable=True)
                    if response.status >= 500:
                        raise AIError(f"AI API server error ({response.status}).", retryable=True)
                    if response.status >= 400:
                        raise AIError(f"AI API request failed ({response.status}).", retryable=False)
                    data = json.loads(body)
                    content = data["choices"][0]["message"]["content"]
                    if isinstance(content, list):
                        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                    finish_reason = str((data.get("choices") or [{}])[0].get("finish_reason") or "")
                    value, was_truncated = parse_json_object(str(content))
                    truncated = was_truncated or finish_reason == "length"
                    if truncated and not is_last_attempt:
                        # Don't silently hand back a cut-off Notes/quiz file.
                        # Grow the token budget and try again for real content.
                        request_max_tokens = min(16000, int(request_max_tokens * 1.5))
                        last_error = AIError("AI response was cut off (token limit) — retrying with a larger budget.", retryable=True)
                        raise last_error
                    logger.info("AI call attempt %s/%s succeeded (%.0fs)", attempt + 1, MAX_AI_RETRIES, time.monotonic() - call_started)
                    return value
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
                last_error = AIError(f"AI response/network error: {type(exc).__name__}", retryable=True)
            except AIError as exc:
                last_error = exc
                if not exc.retryable:
                    break
            if attempt < MAX_AI_RETRIES - 1 and (last_error is None or last_error.retryable):
                await asyncio.sleep(min(30, 2 ** attempt))
        raise last_error or AIError("AI request failed.")


def parse_json_object(raw: str) -> tuple[dict[str, Any], bool]:
    """Returns (value, was_truncated). was_truncated=True means the direct
    json.loads() failed and repair_truncated_json() had to salvage a partial
    object — the caller should treat this as "not really done" and retry
    with a bigger token budget rather than silently shipping cut-off content."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        was_truncated = False
    except json.JSONDecodeError:
        was_truncated = True
        start = cleaned.find("{")
        if start < 0:
            raise AIError("AI returned malformed JSON.", retryable=True)
        candidate = cleaned[start:]
        end = candidate.rfind("}")
        try:
            value = json.loads(candidate[: end + 1]) if end > 0 else None
        except json.JSONDecodeError:
            value = None
        if value is None:
            value = repair_truncated_json(candidate)
        if value is None:
            raise AIError("AI returned malformed JSON (likely cut off — response was too long for the token limit).", retryable=True)
    if not isinstance(value, dict):
        raise AIError("AI returned JSON with the wrong shape.", retryable=True)
    return value, was_truncated


def repair_truncated_json(candidate: str) -> Optional[dict[str, Any]]:
    """Best-effort repair for JSON that was cut off mid-generation (e.g. hit
    the token limit while writing a long notes/quiz object). Trims back to the
    last fully-closed value and re-balances brackets/quotes so the caller still
    gets whatever content was successfully generated, instead of losing the
    whole job."""
    text = candidate
    # If a string was left open, drop everything after the last quote that
    # started it so we don't end up with a dangling unterminated string.
    if text.count('"') % 2 == 1:
        text = text[: text.rfind('"')]
    # Trim to the last point where a value cleanly ended (comma, closing
    # bracket/brace) so we don't keep a half-written key or value.
    last_safe = max(text.rfind(","), text.rfind("}"), text.rfind("]"))
    if last_safe <= 0:
        return None
    text = text[: last_safe + 1]
    if text.rstrip().endswith(","):
        text = text.rstrip()[:-1]
    # Re-balance any unclosed brackets/braces (ignoring ones inside strings).
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    closers = {"{": "}", "[": "]"}
    text += "".join(closers[ch] for ch in reversed(stack))
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


# ============================================================================ #
# STANDALONE HTML BUILDERS
# ============================================================================ #


BASE_CSS = """
:root{--ink:#132238;--muted:#617189;--brand:#6d4aff;--brand2:#15b8a6;--paper:#f7f9fc;--line:#dfe7f1;--good:#138a67;--bad:#c03b50;--warn:#c98a12}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:'Inter',ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.65}
.wrap{max-width:980px;margin:0 auto;padding:28px 18px 64px}.hero{padding:28px;border-radius:24px;color:#fff;background:linear-gradient(135deg,#172c4b,#6d4aff 65%,#15b8a6);box-shadow:0 16px 40px #172c4b24}.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:.75rem;font-weight:800;opacity:.82}.hero h1{margin:.25rem 0;font-size:clamp(1.7rem,4vw,3rem);line-height:1.15}.meta{opacity:.9;display:flex;gap:8px;flex-wrap:wrap;font-size:.9rem}.pill{display:inline-block;padding:4px 10px;border:1px solid #ffffff45;border-radius:999px}
main{margin-top:22px}.section{background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;margin:16px 0;box-shadow:0 6px 20px #1322380a}.section h2{margin-top:0;font-size:1.3rem}.muted{color:var(--muted)}.callout{border-left:4px solid var(--brand2);background:#e9fbf7;padding:14px 16px;border-radius:0 12px 12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.card{border:1px solid var(--line);border-radius:14px;padding:15px}.formula{background:#f0edff;border:1px solid #d9d0ff;border-radius:12px;padding:12px;font-family:ui-monospace,SFMono-Regular,monospace;overflow:auto}.question{border-top:1px solid var(--line);padding:18px 0}.question:first-child{border-top:0}.option{display:flex;align-items:flex-start;gap:10px;width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:10px;margin:7px 0;transition:.15s;cursor:pointer}.option input[type=radio]{margin-top:4px;flex:0 0 auto}.option:hover{border-color:var(--brand);background:#f4f1ff}.answer{color:var(--good);font-weight:700}.warning{background:#fff7e5;border:1px solid #f3d18b;border-radius:12px;padding:12px}.footer{color:var(--muted);font-size:.85rem;text-align:center;margin-top:28px}
button{border:0;border-radius:10px;background:var(--brand);color:#fff;padding:10px 14px;cursor:pointer;font-weight:700;transition:.15s}button:hover{filter:brightness(1.08)}button.secondary{background:#e9edff;color:var(--ink)}.controls{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.palette{display:flex;gap:6px;flex-wrap:wrap}.palette button{min-width:38px;background:#eef0f6;color:var(--ink);border:2px solid transparent}.palette button.answered{background:#d7f6ec;color:var(--good);border-color:var(--good)}.palette button.marked{background:#fff1d6;color:var(--warn);border-color:var(--warn)}.palette button.current{border-color:var(--brand);box-shadow:0 0 0 2px #6d4aff33}
.review{display:none}.review.show{display:block}
.progressbar{height:8px;border-radius:999px;background:#e6e9f2;overflow:hidden;margin:10px 0}.progressbar>div{height:100%;background:linear-gradient(90deg,var(--brand),var(--brand2));transition:width .25s}
.result-correct{color:var(--good)}.result-wrong{color:var(--bad)}
@media(max-width:600px){.wrap{padding:14px 12px 44px}.hero,.section{padding:17px;border-radius:15px}.grid{grid-template-columns:1fr}}
"""

NOTES_CSS = """
.notes-page{background:#fffef6;background-image:repeating-linear-gradient(#fffef6 0 33px,#cfe0f5 33px 34px);background-position-y:8px;border:1px solid #ecdfb8;border-radius:16px;padding:22px 22px 22px 46px;margin:16px 0;position:relative;box-shadow:0 8px 22px #1322380f}
.notes-page::before{content:'';position:absolute;left:26px;top:0;bottom:0;width:2px;background:#ffb9c6}
.notes-page h2{font-family:'Kalam',cursive;color:#a8501c;font-size:1.5rem;text-decoration:underline wavy #ffd166 2px}
.notes-page>div{font-size:1.03rem}
.sticky{border-radius:10px;padding:14px 16px;box-shadow:2px 4px 10px #00000018;margin:14px 0}
.sticky.yellow{background:#fff6b8;transform:rotate(-.6deg)}
.sticky.pink{background:#ffe1ec;transform:rotate(.5deg)}
.sticky.blue{background:#dff1ff;transform:rotate(-.4deg)}
.sticky h2{font-family:'Kalam',cursive;margin-top:0}
.hl{background:linear-gradient(120deg,#fff59d 0 100%);background-repeat:no-repeat;background-size:100% 45%;background-position:0 85%;padding:0 2px}
"""


def notes_section_html(index: int, title: str, content: str) -> str:
    colors = ["#eef2ff", "#eafaf3", "#fff7ea", "#fdeef7"]
    return f'<section class="notes-page" style="background-color:{colors[index % len(colors)]}"><h2>{title}</h2><div>{content}</div></section>'



def page_shell(title: str, subtitle: str, exam: str, language: str, body: str, script: str = "", theme: str = "classic") -> str:
    extra_css = NOTES_CSS if theme == "notes" else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Kalam:wght@400;700&display=swap" rel="stylesheet">
<style>{BASE_CSS}{extra_css}</style></head>
<body><div class="wrap"><header class="hero"><div class="eyebrow">{html.escape(ACADEMY_NAME)}</div>
<h1>{html.escape(title)}</h1><div class="meta"><span class="pill">{html.escape(exam)}</span><span class="pill">{html.escape(language)}</span><span class="pill">{html.escape(subtitle)}</span></div></header>
<main>{body}</main><div class="footer">Prepared for educational practice. Verify official syllabi and patterns with the relevant authority.</div></div>
<script>{script}</script></body></html>"""


def format_text(raw: Any) -> str:
    """Escape untrusted text for HTML, then turn AI markdown (**bold**, *italic*)
    into real tags and newlines into <br>. Every place that shows AI-written
    prose to the user should go through this instead of bare html.escape, or
    the person just sees literal ** characters and stray newlines."""
    text = str(raw) if raw is not None else ""
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = escaped.replace("\n", "<br>")
    return escaped


def flatten_item_to_text(item: Any) -> str:
    """Turn one list entry from the AI into plain readable text, whatever
    shape it came back in. The AI is asked for plain strings in lists like
    key_concepts/important_facts, but sometimes still returns structured
    objects like {"concept": "...", "content": "..."} — without this, that
    dict was being dumped with Python's str(dict) straight into the page
    (visible as literal {'concept': '...', 'content': '...'} text)."""
    if isinstance(item, dict):
        head = item.get("concept") or item.get("term") or item.get("label") or item.get("title") or item.get("name") or item.get("point")
        body = (
            item.get("content")
            or item.get("definition")
            or item.get("value")
            or item.get("description")
            or item.get("explanation")
            or item.get("detail")
            or item.get("text")
        )
        if head and body and str(head).strip() != str(body).strip():
            return f"**{head}**: {body}"
        if body:
            return str(body)
        if head:
            return str(head)
        parts = [str(v) for v in item.values() if isinstance(v, (str, int, float)) and str(v).strip()]
        return " — ".join(parts)
    if isinstance(item, list):
        return ", ".join(flatten_item_to_text(sub) for sub in item if flatten_item_to_text(sub))
    return str(item) if item is not None else ""


def safe_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = flatten_item_to_text(item).strip()
        if text:
            out.append(text)
    return out


def normalize_test_questions(items: Any) -> list[dict[str, Any]]:
    """Normalize common AI field names into the exact test-player shape."""
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("question") or item.get("text") or item.get("prompt") or "").strip()
        raw_options = item.get("options") or item.get("choices") or item.get("answers") or {}
        options: dict[str, str] = {}
        if isinstance(raw_options, list):
            options = {chr(65 + index): str(value) for index, value in enumerate(raw_options[:4])}
        elif isinstance(raw_options, dict):
            for key, value in raw_options.items():
                key_text = str(key).strip().upper()
                if key_text in {"A", "B", "C", "D"}:
                    options[key_text] = str(value)
        answer = str(
            item.get("answer")
            or item.get("correct_answer")
            or item.get("correctAnswer")
            or item.get("correct_option")
            or item.get("correctOption")
            or item.get("correct")
            or ""
        ).strip()
        answer_upper = answer.upper()
        if answer_upper in options:
            answer = answer_upper
        else:
            for key, value in options.items():
                if answer.casefold() == value.casefold():
                    answer = key
                    break
        explanation = str(
            item.get("explanation")
            or item.get("solution")
            or item.get("answer_explanation")
            or item.get("reason")
            or ""
        ).strip()
        normalized.append(
            {
                "question": prompt,
                "options": options,
                "answer": answer,
                "explanation": explanation,
            }
        )
    return normalized


def build_notes(data: dict[str, Any], row: sqlite3.Row) -> str:
    sections = []
    for index, section in enumerate(data.get("sections", [])):
        if isinstance(section, dict):
            title = html.escape(str(section.get("title", "Key Concept")))
            content = format_text(section.get("content", ""))
            sections.append(notes_section_html(index, title, content))
    facts = "".join(f"<li>{format_text(item)}</li>" for item in safe_list(data.get("important_facts")))
    mistakes = "".join(f"<li>{format_text(item)}</li>" for item in safe_list(data.get("common_mistakes")))
    formulas = "".join(f'<div class="formula">{format_text(item)}</div>' for item in safe_list(data.get("formulas")))
    extra = ""
    if facts:
        extra += f'<div class="sticky yellow"><h2>Important facts</h2><ul>{facts}</ul></div>'
    if formulas:
        extra += f'<div class="sticky blue"><h2>Formulas and relationships</h2>{formulas}</div>'
    if mistakes:
        extra += f'<div class="sticky pink"><h2>Common mistakes</h2><ul>{mistakes}</ul></div>'
    return page_shell(str(data.get("title", row["topic"])), "Notes", row["exam"], row["language"], "".join(sections) + extra, theme="notes")


def build_revision(data: dict[str, Any], row: sqlite3.Row) -> str:
    groups = []
    for label, key in [("Definitions", "definitions"), ("Key concepts", "key_concepts"), ("Important facts", "important_facts"), ("Memory aids", "memory_aids"), ("Exam tips", "exam_tips"), ("Common traps", "common_traps")]:
        values = "".join(f"<li>{format_text(value)}</li>" for value in safe_list(data.get(key)))
        if values:
            groups.append(f'<section class="section"><h2>{label}</h2><ul>{values}</ul></section>')
    return page_shell(str(data.get("title", row["topic"])), "Quick Revision", row["exam"], row["language"], "".join(groups))


def question_html(question: dict[str, Any], number: int, show_answer: bool = True) -> str:
    options = "".join(f'<div class="option"><b>{html.escape(str(label))}.</b> {format_text(value)}</div>' for label, value in (question.get("options") or {}).items())
    answer = f'<div class="answer">Answer: {html.escape(str(question.get("answer", "")))}</div>' if show_answer else ""
    explanation = f'<p class="muted">{format_text(question.get("explanation", ""))}</p>' if question.get("explanation") else ""
    return f'<article class="question"><h3>{number}. {format_text(question.get("question", ""))}</h3>{options}{answer}{explanation}</article>'


def build_practice(data: dict[str, Any], row: sqlite3.Row, label: str = "Practice") -> str:
    questions = [item for item in data.get("questions", []) if isinstance(item, dict)]
    body = f'<section class="section"><p class="muted">{format_text(data.get("instructions", "Attempt each question before checking the explanation."))}</p>{"".join(question_html(q, i + 1) for i, q in enumerate(questions))}</section>'
    return page_shell(str(data.get("title", row["topic"])), label, row["exam"], row["language"], body)


def build_formula_sheet(data: dict[str, Any], row: sqlite3.Row) -> str:
    cards = []
    for formula in data.get("formulas", []):
        if not isinstance(formula, dict):
            continue
        expr = format_text(formula.get("formula", ""))
        rows = []
        if formula.get("symbols"):
            rows.append(f'<p><b>Symbols:</b> {format_text(formula.get("symbols"))}</p>')
        if formula.get("unit"):
            rows.append(f'<p><b>Unit:</b> {format_text(formula.get("unit"))}</p>')
        if formula.get("use_case"):
            rows.append(f'<p><b>When to use:</b> {format_text(formula.get("use_case"))}</p>')
        if formula.get("conditions"):
            rows.append(f'<p class="muted"><b>Conditions:</b> {format_text(formula.get("conditions"))}</p>')
        if formula.get("common_mistake"):
            rows.append(f'<p class="muted"><b>Common mistake:</b> {format_text(formula.get("common_mistake"))}</p>')
        cards.append(f'<div class="card"><div class="formula">{expr}</div>{"".join(rows)}</div>')
    body = f'<section class="section"><div class="grid">{"".join(cards)}</div></section>'
    return page_shell(str(data.get("title", row["topic"])), "Formula Sheet", row["exam"], row["language"], body)


def build_flashcards(data: dict[str, Any], row: sqlite3.Row) -> str:
    cards = []
    for index, card in enumerate(data.get("cards", []), 1):
        if not isinstance(card, dict):
            continue
        front = html.escape(str(card.get("front", "")))
        back = html.escape(str(card.get("back", "")))
        cards.append(f'<div class="card"><h3>Card {index}</h3><p><b>{front}</b></p><p class="muted">{back}</p></div>')
    body = f'<section class="section"><div class="grid">{"".join(cards)}</div></section>'
    return page_shell(str(data.get("title", row["topic"])), "Flashcards", row["exam"], row["language"], body)


def build_answer_writing(data: dict[str, Any], row: sqlite3.Row) -> str:
    prompts = []
    for prompt in data.get("prompts", []):
        if not isinstance(prompt, dict):
            continue
        prompts.append(f'<div class="section"><h2>{html.escape(str(prompt.get("question", "Answer-writing prompt")))}</h2><p class="muted">Suggested points</p><ul>{"".join(f"<li>{html.escape(x)}</li>" for x in safe_list(prompt.get("suggested_points")))}</ul></div>')
    return page_shell(str(data.get("title", row["topic"])), "Answer Writing", row["exam"], row["language"], "".join(prompts))


def build_test(data: dict[str, Any], row: sqlite3.Row) -> str:
    questions = normalize_test_questions(data.get("questions", []))
    encoded = json.dumps(
        [{"question": str(q.get("question", "")), "options": q.get("options") or {}, "answer": str(q.get("answer", "")), "explanation": str(q.get("explanation", ""))} for q in questions],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    body = f"""
    <section class="section"><p class="muted">{html.escape(str(data.get("instructions", "Choose an answer, then submit when you are ready.")))}</p>
    <div id="timer" class="callout">Time remaining: <b>--:--</b></div>
    <div class="progressbar"><div id="progress" style="width:0%"></div></div>
    <div id="palette" class="palette"></div>
    <div id="test"></div><div class="controls"><button id="prev" class="secondary">Previous</button><button id="clear" class="secondary">Clear answer</button><button id="mark" class="secondary">Mark for review</button><button id="next">Next</button><button id="submit">Submit</button></div>
    <div id="result" class="review"></div></section>
    """
    script = f"""const questions={encoded};let current=0,answers=Array(questions.length).fill(null),marked=new Set(),submitted=false;
const test=document.getElementById('test'),palette=document.getElementById('palette'),result=document.getElementById('result'),progress=document.getElementById('progress');
function renderPalette(){{palette.innerHTML=questions.map((_,i)=>`<button class="${{answers[i]!==null?'answered':''}} ${{marked.has(i)?'marked':''}} ${{i===current?'current':''}}" data-i="${{i}}">${{i+1}}</button>`).join('');palette.querySelectorAll('button').forEach(b=>b.onclick=()=>{{current=+b.dataset.i;render()}});const done=answers.filter(a=>a!==null).length;progress.style.width=(questions.length?Math.round(done/questions.length*100):0)+'%'}}
function render(){{const q=questions[current]||{{}};test.innerHTML=`<article class="question"><h2>Question ${{current+1}} of ${{questions.length}}</h2><p>${{q.question||''}}</p>${{Object.entries(q.options||{{}}).map(([k,v])=>`<label class="option"><input type="radio" name="answer" value="${{k}}" ${{answers[current]===k?'checked':''}}> <b>${{k}}.</b> ${{v}}</label>`).join('')}}<p class="muted">${{marked.has(current)?'Marked for review':''}}</p></article>`;test.querySelectorAll('input').forEach(input=>input.onchange=()=>{{answers[current]=input.value;renderPalette()}});renderPalette()}}
document.getElementById('prev').onclick=()=>{{current=Math.max(0,current-1);render()}};document.getElementById('next').onclick=()=>{{current=Math.min(questions.length-1,current+1);render()}};
document.getElementById('clear').onclick=()=>{{answers[current]=null;render()}};document.getElementById('mark').onclick=()=>{{marked.has(current)?marked.delete(current):marked.add(current);render()}};
document.getElementById('submit').onclick=()=>{{submitted=true;let correct=0,wrong=0,skipped=0;questions.forEach((q,i)=>answers[i]===null?skipped++:answers[i]===q.answer?correct++:wrong++);const accuracy=correct+wrong?Math.round(correct/(correct+wrong)*100):0;result.className='review show';result.innerHTML=`<h2>Result</h2><div class="grid"><div class="card result-correct"><b>${{correct}}</b><br>Correct</div><div class="card result-wrong"><b>${{wrong}}</b><br>Wrong</div><div class="card"><b>${{skipped}}</b><br>Skipped</div><div class="card"><b>${{accuracy}}%</b><br>Accuracy</div></div><div>${{questions.map((q,i)=>questionHtmlForReview(q,i)).join('')}}</div>`;window.scrollTo({{top:document.body.scrollHeight,behavior:'smooth'}})}};
function questionHtmlForReview(q,i){{const correct=answers[i]===q.answer;return `<article class="question"><h3>${{i+1}}. ${{q.question}}${{marked.has(i)?' <span class="muted">(marked)</span>':''}}</h3><p class="${{answers[i]===null?'':(correct?'result-correct':'result-wrong')}}">Your answer: ${{answers[i]||'Skipped'}} | Correct: ${{q.answer}}</p><p class="muted">${{q.explanation||''}}</p></article>`}}
let remaining=Number({int(data.get('duration_minutes', 0) or 0)})*60;setInterval(()=>{{if(!submitted&&remaining>0){{remaining--;document.querySelector('#timer b').textContent=`${{Math.floor(remaining/60)}}:${{String(remaining%60).padStart(2,'0')}}`}}}},1000);render();"""
    # questionHtmlForReview is intentionally defined in the script; no server JS is required.
    return page_shell(str(data.get("title", row["topic"])), resource_label(row["resource_type"]), row["exam"], row["language"], body, script)


def build_html(data: dict[str, Any], row: sqlite3.Row) -> str:
    kind = row["resource_type"]
    if kind == "Notes":
        return build_notes(data, row)
    if kind == "Quick-Revision":
        return build_revision(data, row)
    if kind == "Formula-Sheet":
        return build_formula_sheet(data, row)
    if kind in QUESTION_RESOURCE_TYPES:
        # Every question-based resource is now the interactive quiz player
        # (palette, timer, submit-then-review) — never a page that shows the
        # answer directly under each question. Practice/PYQ used to render
        # via build_practice() with the answer visible immediately, which is
        # the "solved question file" that should not exist anymore.
        return build_test(data, row)
    if kind == "Flashcards":
        return build_flashcards(data, row)
    if kind == "Answer-Writing":
        return build_answer_writing(data, row)
    return build_notes(data, row)


# ============================================================================ #
# ACADEMY HUBS — self-contained index.html pages over the OUTPUT library
# (one per exam + one root hub), so the generated folder reads like the
# PrepGridOfficial academy website instead of a raw pile of files.
# ============================================================================ #


HUB_CSS = """
:root{--ink:#132238;--muted:#6b7a90;--brand:#4f46e5;--brand2:#0ea5e9;--paper:#f5f7fb;--line:#e2e8f0;--card:#fff}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--paper);color:var(--ink);font-family:'Inter',ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.6}
a{text-decoration:none;color:inherit}
.hero{padding:36px 20px 30px;color:#fff;background:radial-gradient(900px 360px at 15% -10%,rgba(255,255,255,.22),transparent),linear-gradient(135deg,#0f172a,#4f46e5 55%,#0ea5e9);}
.wrap{max-width:1080px;margin:0 auto}
.eyebrow{font-size:.7rem;letter-spacing:.22em;text-transform:uppercase;opacity:.85;font-weight:800}
h1{font-size:clamp(1.7rem,4.4vw,2.7rem);margin:.25rem 0 .15rem;line-height:1.15}
.sub{opacity:.92;font-size:.95rem;max-width:760px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.chip{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:5px 13px;font-size:.76rem;font-weight:700}
.back{margin-top:14px;display:inline-flex;gap:6px;align-items:center;font-size:.8rem;font-weight:700;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:6px 13px}
.back:hover{background:rgba(255,255,255,.26)}
.stick{position:sticky;top:0;z-index:6;background:rgba(245,247,251,.92);backdrop-filter:blur(9px);border-bottom:1px solid var(--line)}
.controls{max-width:1080px;margin:0 auto;display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:12px 20px}
.controls input,.controls select{padding:10px 13px;border-radius:12px;border:1px solid var(--line);font-size:.9rem;background:#fff;outline:none;color:inherit}
.controls input{flex:1;min-width:180px}
.controls input:focus,.controls select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(79,70,229,.15)}
.controls select{max-width:230px}
.count{font-size:.8rem;color:var(--muted);font-weight:700;white-space:nowrap}
.grid{max-width:1080px;margin:0 auto;padding:22px 20px 70px;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.fcard{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:15px;padding:14px 15px;transition:.16s;box-shadow:0 2px 8px rgba(15,23,42,.04)}
.fcard:hover{border-color:var(--brand);transform:translateY(-2px);box-shadow:0 10px 24px rgba(15,23,42,.12)}
.fcard .kind{font-size:.64rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#4f46e5;margin-bottom:7px}
.fcard .tname{font-weight:700;font-size:.95rem;line-height:1.4}
.fcard .meta{margin-top:auto;padding-top:9px;font-size:.72rem;color:var(--muted)}
.fcard .meta b{color:#334155}
.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:44px 0}
.exam-ico{width:46px;height:46px;border-radius:13px;background:linear-gradient(135deg,#4f46e5,#0ea5e9);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.15rem;color:#fff;margin-bottom:10px}
@media(max-width:600px){.hero{padding:26px 16px}.controls{padding:10px 12px}.grid{padding:16px 12px 54px}}
"""

HUB_JS = """const data=JSON.parse(document.getElementById('hubdata').textContent);
const box=document.getElementById('cards'),q=document.getElementById('q'),sub=document.getElementById('s'),typ=document.getElementById('t'),cnt=document.getElementById('cnt');
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function titleOf(name){return name.replace(/\\.html$/i,'').replace(/-/g,' ');}
function render(){const f=q.value.toLowerCase().trim(),ss=sub.value,ts=typ.value;let n=0;
const html=data.map(it=>{if(ss&&it.subject!==ss)return '';if(ts&&it.kind!==ts)return '';if(f&&!(it.subject+' '+it.kind+' '+it.name).toLowerCase().includes(f))return '';
n++;return '<a class="fcard" target="_blank" rel="noopener" href="'+esc(it.rel)+'"><div class="kind">'+esc(it.kind)+'</div><div class="tname">'+esc(titleOf(it.name))+'</div><div class="meta"><b>'+esc(it.subject)+'</b> · open file</div></a>';}).join('');
box.innerHTML=html||'<div class="empty">No files match this filter.</div>';cnt.textContent=n+' file'+(n===1?'':'s');
}
q.oninput=render;sub.onchange=render;typ.onchange=render;render();
"""

HUB_ACADEMY_JS = """const data=JSON.parse(document.getElementById('hubdata').textContent);
const box=document.getElementById('cards'),q=document.getElementById('q'),cnt=document.getElementById('cnt');
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function render(){const f=q.value.toLowerCase().trim();let n=0;
const html=data.map(it=>{if(f&&!(it.name+' '+it.subjects.join(' ')).toLowerCase().includes(f))return '';
n++;return '<a class="fcard" href="'+esc(it.href)+'"><div class="exam-ico">'+esc(it.mark)+'</div><div class="tname">'+esc(it.name)+'</div><div class="meta"><b>'+it.files+'</b> files · '+esc(it.subjects.join(', '))+'</div></a>';}).join('');
box.innerHTML=html||'<div class="empty">No exams match.</div>';cnt.textContent=n+' exam'+(n===1?'':'s');
}
q.oninput=render;render();
"""


def exam_files_flat(exam: str) -> list[dict[str, str]]:
    """Walk one exam's OUTPUT folder and return every generated HTML file as
    {subject, kind, name, rel} sorted for stable ordering. The exam's own hub
    (index.html at the folder root) is intentionally excluded."""
    base = Path(OUTPUT_DIR) / safe_filename(exam)
    items: list[dict[str, str]] = []
    if not base.is_dir():
        return items
    for subject_dir in sorted(base.iterdir()):
        if not subject_dir.is_dir():
            continue
        for kind_dir in sorted(subject_dir.iterdir()):
            if not kind_dir.is_dir():
                continue
            for file_path in sorted(kind_dir.glob("*.html")):
                rel = file_path.relative_to(base).as_posix()
                items.append(
                    {"subject": subject_dir.name, "kind": kind_dir.name,
                     "name": file_path.name, "rel": rel}
                )
    return items


def exam_html_files(exam: str) -> list[Path]:
    """Every HTML file under this exam's OUTPUT folder (including its hub), for
    ZIP building."""
    base = Path(OUTPUT_DIR) / safe_filename(exam)
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.html") if p.is_file())


def hub_page(head_title: str, eyebrow: str, title: str, subtitle: str,
             chips: list[str], body: str, items_json: str, use_academy_js: bool = False) -> str:
    script = HUB_ACADEMY_JS if use_academy_js else HUB_JS
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(head_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{HUB_CSS}</style></head>
<body>
<header class="hero"><div class="wrap">
<div class="eyebrow">{html.escape(eyebrow)}</div>
<h1>{html.escape(title)}</h1>
<p class="sub">{html.escape(subtitle)}</p>
<div class="chips">{''.join(f'<span class="chip">{html.escape(c)}</span>' for c in chips)}</div>
</div></header>
<div class="stick"><div class="controls">
<input id="q" type="search" placeholder="Search files…" autocomplete="off">
{body}
<span class="count" id="cnt"></span>
</div></div>
<div class="grid" id="cards"></div>
<script id="hubdata" type="application/json">{items_json}</script>
<script>{script}</script>
</body></html>"""


def build_exam_hub(exam: str) -> dict[str, Any]:
    """Write OUTPUT/<exam>/index.html — a searchable hub over every generated
    file for this exam. Returns small stats for reporting."""
    items = exam_files_flat(exam)
    subjects = sorted({item["subject"] for item in items})
    kinds = sorted({item["kind"] for item in items})
    chips = [f"{exam}", f"{len(items)} files", f"{len(subjects)} subjects", f"{len(kinds)} resource types", "Updated just now"]
    select = '<select id="s" aria-label="Subject"><option value="">All subjects</option>' + "".join(f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in subjects) + "</select>"
    type_select = '<select id="t" aria-label="Resource type"><option value="">All types</option>' + "".join(f'<option value="{html.escape(k)}">{html.escape(k)}</option>' for k in kinds) + "</select>"
    body = select + type_select
    page = hub_page(
        f"{exam} Study Hub — {ACADEMY_NAME}",
        ACADEMY_NAME,
        f"{exam} — Complete Study Hub",
        f"Every generated resource for {exam}: full notes, quick revision, formula sheets, tests, PYQ practice and mocks — tap any card to open it.",
        chips,
        body,
        json_text(items),
    )
    output = Path(OUTPUT_DIR) / safe_filename(exam) / HUB_FILENAME
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return {"exam": exam, "files": len(items), "subjects": subjects}


def build_academy_hub() -> dict[str, Any]:
    """Write OUTPUT/index.html — the root academy page linking every exam hub
    that has at least one generated file."""
    rows: list[dict[str, Any]] = []
    total_files = 0
    for exam in EXAM_CONFIG:
        files = exam_files_flat(exam)
        if not files:
            continue
        total_files += len(files)
        subjects: list[str] = []
        for item in files:
            if item["subject"] not in subjects:
                subjects.append(item["subject"])
        rows.append(
            {"name": exam, "href": f"{safe_filename(exam)}/{HUB_FILENAME}",
             "files": len(files), "subjects": subjects,
             "mark": (exam[:1].upper() or "E")}
        )
    rows.sort(key=lambda r: r["name"].casefold())
    if not rows:
        return {"exams": 0, "files": 0}
    select = '<select id="s" style="display:none"></select>'
    body = select + '<a class="back" href=".">⬆ Library root</a>'
    page = hub_page(
        f"{ACADEMY_NAME} — Resource Library",
        ACADEMY_NAME,
        "Complete Resource Library",
        f"{ACADEMY_TAGLINE} Every exam has its own folder and hub — open an exam card to browse notes, revisions, tests and mocks.",
        [f"{len(rows)} exams", f"{total_files} files"],
        body,
        json_text(rows),
        use_academy_js=True,
    )
    (Path(OUTPUT_DIR) / HUB_FILENAME).write_text(page, encoding="utf-8")
    return {"exams": len(rows), "files": total_files}


# ============================================================================ #
# GENERATION ENGINE
# ============================================================================ #


GENERATOR_SYSTEM = """You generate structured educational content for Sonic Resource Factory,
a platform serving MANY different exams (NEET, JEE, GUJCET, GSEB board exams, GPSC, UPSC, SSC,
Railway/RRB, Banking, Talati, GSSSB, Gujarat Police, TET-1, TET-2, TAT, HTAT, CA, CS, CMA, and any
future exam added to the platform's exam list). You are not given hand-written subject rules for
every exam — instead you must figure out, from the exam name + subject + topic given to you, what
kind of content is actually appropriate, the same way an experienced faculty member for that exact
exam would. Get this right without being told explicitly:

- Identify the NATURE of the subject/topic yourself before writing anything:
  * Formula/numerical subjects (Physics, Chemistry-physical, Mathematics, Reasoning-quant,
    Statistics, Accountancy/Costing for CA/CS/CMA): lead with formulas, variables, units,
    derivations/conditions, worked numericals, common calculation mistakes.
  * Reaction/mechanism subjects (Organic/Inorganic Chemistry): reactions, reagents, conditions,
    conversions, exceptions and trends — not generic formulas.
  * Descriptive/factual subjects (Biology, History, Geography, Polity, Economy, General Studies,
    General Knowledge, Static GK, Current Affairs, Reasoning-verbal, English/Language, Law,
    Sociology, Public Administration, teaching-methodology papers for TET/TAT/HTAT): lead with
    definitions, processes, causes/effects, classifications, important facts, dates/figures where
    genuinely part of the syllabus, and high-yield revision points. Do not force a "formula"
    section onto a subject that does not have formulas.
  * Skill/aptitude subjects (Reasoning, English comprehension, Quantitative Aptitude for
    SSC/Banking/Railway/Talati/GSSSB): focus on solving technique, shortcuts, common trap
    patterns, and worked examples over pure theory.
  * Professional/technical papers (CA/CS/CMA — Accounts, Law, Audit, Tax, Costing): use correct
    professional terminology, sections/standards by name where standard and well-known, and
    practical worked treatment; do not oversimplify into school-level language.
- Match the DEPTH and QUESTION STYLE to the exam's actual difficulty level: a Talati/GSSSB clerical
  exam needs simpler, direct-recall content; UPSC/GPSC needs analytical, statement-based,
  multi-concept questions; NEET/JEE needs high-difficulty application and numerical questions;
  TET/TAT/HTAT needs pedagogy-aware, child-development-aware framing for the teaching-methodology
  portions and subject-accurate content for the subject portions.
- Stay strictly inside the exam+subject+chapter+topic given to you. Never wander into a different
  exam's syllabus emphasis (for example, do not answer a GPSC Gujarat-specific History/Geography
  question with generic national-only facts if the topic is clearly Gujarat-specific, and do not
  answer a Talati/GSSSB question at UPSC depth).

Return ONLY valid JSON, never Markdown and never a JSON code fence.
Respect the requested exam, subject, topic, language, and resource type exactly.
Never invent an official exam pattern, marks, or question count as fact. If official data is not
supplied in the blueprint reference, do not state it as official — write generically instead.
Never call generated questions real previous-year questions. For PYQ without source material, use
the label PYQ-STYLE PRACTICE.
Do not use emojis in generated educational content. Keep explanations accurate, clear, mobile-friendly,
and exam-appropriate.

For "Notes": this must be a COMPLETE study chapter for this single topic, not a short summary.
Cover every standard sub-topic a serious aspirant of THIS exam needs, using the subject-nature
guidance above to decide what "complete" means for this particular topic: definitions, every
important concept in depth (with reasoning/derivation where the subject has that, not just a
one-line statement), every relevant formula with variables explained ONLY if the subject actually
has formulas, worked examples where the subject needs them, labelled diagram descriptions where
visual concepts apply, exam-weightage notes, and common mistakes/confusion points. Write 6-10
sections for a normal-sized topic (more only for unusually large chapters). Each section's "content"
should be a genuinely detailed paragraph or a thorough bullet list — not one line — but stay focused
and avoid needless repetition, because the response has a hard length limit and must be complete
valid JSON; a shorter COMPLETE answer is far better than a longer answer that gets cut off
mid-sentence. Never leave "formulas" or any other array empty just to fill the schema — omit content
that genuinely does not apply to this subject rather than inventing filler.

For any question-based resource (Practice, PYQ, Topic-Test, Chapter-Test, Subject-Test, Full-Mock,
Current-Affairs): write at the genuinely correct difficulty for THIS exam (see depth guidance above)
— never uniformly "textbook-easy recall" and never harder than the exam actually asks.
Every question must be meaningfully different in content from every other question in the same
file — never restate the same fact with different wording. Vary how questions open: do not start
multiple questions with the same opening word or phrase (for example, do not begin question after
question with "Which of the following"); mix question styles appropriate to the exam (assertion-
reason, direct fact, application/numerical, statement-based, match-the-following, case-based) —
only use styles that exam actually uses.
Spread correct answers roughly evenly across A/B/C/D — do not make one option the answer most of
the time.

COMPLETENESS RULE (the single most important rule — applies to EVERY file you produce):
A student who downloads this one file must be able to revise this topic FULLY from it and then
attempt real exam questions on it. Missing even one standard sub-topic counts as a failed file.
- For "Notes" and "Quick-Revision": treat the requested topic as the FULL chapter for this exam's
  syllabus, never as "mention the highlights". Before finishing, silently run a coverage check over
  every sub-part the chapter normally has (for formula subjects: every formula + variables + when to
  use; for reaction subjects: every named reaction, reagent, condition, exception; for factual
  subjects: every definition, classification, list, process, cause-effect pair, and genuinely-in-
  syllabus date/figure) and add whatever is missing. A section is complete only when its "content" is
  multi-paragraph depth or a long, genuinely thorough bullet list — one thin line means the file
  failed. Use 6-10 sections for a normal topic and never stop early just because you are short of
  room; when a topic is huge, keep real depth and drop only padding.
- For any question-based resource: never deliberately thin out a test to save effort. Every question
  must add NEW information (no rephrasing an earlier question), and the whole set must together span
  the breadth of the requested scope so nothing important is left untested.
- PYQ: if a real source file was supplied it is authoritative — transcribe its questions faithfully.
  If no source was supplied, clearly mark the file PYQ-STYLE PRACTICE and never attach a fake year.

RESOURCE-SCOPE AWARENESS (read the Topic line before writing anything):
- A normal Topic means ONE chapter/unit of one subject — stay strictly inside it.
- A Topic like "Complete <Subject> Syllabus" means the WHOLE SUBJECT — span every
  chapter of that subject, never just one chapter.
- A Topic like "<Exam> Complete Syllabus" (used by Full-Mock, Full-Syllabus-Mock,
  Revision-Test and other exam-level files) means the WHOLE EXAM — span every
  subject in that exam's syllabus, in the exam's real proportion and question
  style. Never treat an exam-wide file as a single-topic test, and never let an
  exam-wide test come out thin.

EXAM-SPECIFIC TREATMENT: identify the exam type and teach at that exam's real
level — NEET/JEE: conceptual + application + numerical; UPSC/GPSC:
analytical + factual + descriptive; GSSSB/Talati/Railway/SSC/Banking:
direct-recall, reasoning and shortcut technique at the clerical/competitive level;
TET/TAT/HTAT: pedagogy- and child-development-aware for methodology papers;
CA/CS/CMA: professional standards and terminology; GSEB board: curriculum/
board-oriented. The blueprint reference is context only — never state a syllabus,
marks, pattern, question count or eligibility as OFFICIAL unless the blueprint
field is editor-verified; otherwise write generically and mark uncertainty."""


def schema_for(resource_type: str, count: int) -> str:
    if resource_type == "Notes":
        return '{"title":"...","sections":[{"title":"...","content":"Several detailed paragraphs or a thorough bullet list — full depth, not a summary"}],"important_facts":["..."],"formulas":["...","include every relevant formula for this topic, not just one or two"],"common_mistakes":["..."]}'
    if resource_type == "Quick-Revision":
        return '{"title":"...","definitions":["..."],"key_concepts":["..."],"important_facts":["..."],"memory_aids":["..."],"common_traps":["..."],"exam_tips":["..."]}'
    if resource_type == "Formula-Sheet":
        return '{"title":"...","formulas":[{"formula":"the formula itself, in standard mathematical notation","symbols":"what each symbol/variable means","unit":"SI unit(s), or omit if not applicable","use_case":"when/why this formula is used","conditions":"conditions or assumptions this formula requires, if any","common_mistake":"a common mistake students make with this formula"}]}'
    if resource_type == "Flashcards":
        return '{"title":"...","cards":[{"front":"...","back":"..."}]}'
    if resource_type == "Answer-Writing":
        return '{"title":"...","prompts":[{"question":"...","suggested_points":["..."]}]}'
    return '{"title":"...","instructions":"...","duration_minutes":0,"questions":[{"question":"...","options":{"A":"...","B":"...","C":"...","D":"..."},"answer":"A","explanation":"..."}]}'


def validate_content(data: dict[str, Any], resource_type: str) -> None:
    if not str(data.get("title", "")).strip():
        raise AIError("AI JSON is missing title.", retryable=True)
    if resource_type in {"Notes", "Quick-Revision"} and not (data.get("sections") or data.get("definitions") or data.get("key_concepts")):
        raise AIError("AI JSON has no educational content.", retryable=True)
    if resource_type == "Formula-Sheet" and not isinstance(data.get("formulas"), list):
        raise AIError("AI JSON has no formulas.", retryable=True)
    if resource_type == "Flashcards" and not isinstance(data.get("cards"), list):
        raise AIError("AI JSON has no flashcards.", retryable=True)
    if resource_type == "Answer-Writing" and not isinstance(data.get("prompts"), list):
        raise AIError("AI JSON has no answer-writing prompts.", retryable=True)
    if resource_type in QUESTION_RESOURCE_TYPES:
        questions = data.get("questions")
        if not isinstance(questions, list) or not questions:
            raise AIError("AI JSON has no questions.", retryable=True)
        for question in questions:
            if not is_complete_question(question):
                raise AIError("AI JSON contains an incomplete question (missing options/answer).", retryable=True)
        seen_check: set[str] = set()
        for question in questions:
            norm = normalize_question(str(question.get("question", "")))
            if norm and norm in seen_check:
                raise AIError("AI JSON contains a duplicate question within the same file.", retryable=True)
            if norm:
                seen_check.add(norm)


async def extract_source(path: Optional[str]) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if file_path.suffix.lower() in {".txt", ".md", ".csv"}:
        return file_path.read_text(encoding="utf-8", errors="replace")[:40000]
    if file_path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)[:40000]
        except Exception as exc:
            raise AIError(f"Could not extract PDF text: {type(exc).__name__}", retryable=False)
    return ""


async def filter_unique_questions(db: Database, row: sqlite3.Row, data: dict[str, Any], ai: AIClient) -> dict[str, Any]:
    if row["resource_type"] not in QUESTION_RESOURCE_TYPES:
        return data
    accepted: list[dict[str, Any]] = []
    known = await db.similar_questions("", 200)
    generation_id = uuid.uuid4().hex
    for question in data.get("questions", []):
        normalized = normalize_question(str(question.get("question", "")))
        if not normalized:
            continue
        question_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        too_similar = any(SequenceMatcher(None, normalized, old).ratio() >= QUESTION_SIMILARITY_THRESHOLD for old in known)
        if too_similar or await db.question_exists(question_hash):
            logger.warning("Duplicate question rejected for topic %s", row["topic"])
            continue
        if await db.save_question(row, question, generation_id):
            accepted.append(question)
            known.append(normalized)
    data["questions"] = accepted
    return data


# ─── Language-aware batching (mirrors what alexa-7.py already does reliably
# for Gujarati mock tests: smaller batches + more tokens/question + its own
# timeout + lower temperature for Indic scripts) ──────────────────────────────
LANG_CHUNK_SIZE = {"gujarati": 5, "hindi": 5, "english": 12}
LANG_TOKENS_PER_Q = {"gujarati": 650, "hindi": 650, "english": 300}
LANG_TEMPERATURE = {"gujarati": 0.3, "hindi": 0.3, "english": 0.5}
LANG_TIMEOUT_BASE = {"gujarati": 90.0, "hindi": 90.0, "english": 60.0}

GUJARATI_GLOSSARY = """Reference Gujarati scientific/exam terms (use these exact terms for consistency):
કોષ (Cell), કોષકેન્દ્ર (Nucleus), ઉત્સેચક (Enzyme), વર્ણસૂત્ર (Chromosome), અનુવંશિકતા (Heredity),
પ્રકાશસંશ્લેષણ (Photosynthesis), શ્વસન (Respiration), હોર્મોન (Hormone), પેશી (Tissue), અંગ (Organ),
DNA-આરએનએ (DNA-RNA), ઉત્ક્રાંતિ (Evolution), પ્રજનન (Reproduction), ચેતાતંત્ર (Nervous system),
પરિવહન (Transport), ઉત્સર્જન (Excretion), પ્રતિરક્ષાતંત્ર (Immune system), જનીન (Gene), પ્રોટીન (Protein),
કાર્બોદિત (Carbohydrate), વેગ (Velocity), પ્રવેગ (Acceleration), બળ (Force), ઊર્જા (Energy),
સંવેગ (Momentum), ગુરુત્વાકર્ષણ (Gravitation)."""


def question_chunk_size(language: str) -> int:
    return LANG_CHUNK_SIZE.get(language.strip().lower(), LANG_CHUNK_SIZE["english"])


def question_temperature(language: str) -> float:
    return LANG_TEMPERATURE.get(language.strip().lower(), LANG_TEMPERATURE["english"])


def is_complete_question(question: Any) -> bool:
    """A question is only usable if it has real question text, at least 4
    non-empty options, and an answer that actually points at one of them.
    This is what stops a token-starved AI response (empty options/answer,
    like a Gujarati chunk that ran out of budget) from ever reaching the
    final HTML."""
    if not isinstance(question, dict):
        return False
    qtext = str(question.get("question") or question.get("text") or question.get("prompt") or "").strip()
    if not qtext:
        return False
    raw_options = question.get("options") or question.get("choices") or question.get("answers") or {}
    if isinstance(raw_options, dict):
        option_values = [str(v).strip() for v in raw_options.values() if str(v).strip()]
    elif isinstance(raw_options, list):
        option_values = [str(v).strip() for v in raw_options if str(v).strip()]
    else:
        option_values = []
    if len(option_values) < 4:
        return False
    answer = str(
        question.get("answer")
        or question.get("correct_answer")
        or question.get("correctAnswer")
        or question.get("correct_option")
        or question.get("correctOption")
        or question.get("correct")
        or ""
    ).strip()
    return bool(answer)


def keep_complete_questions(data: dict[str, Any]) -> dict[str, Any]:
    data["questions"] = [q for q in (data.get("questions") or []) if is_complete_question(q)]
    return data


def estimate_generation_params(resource_type: str, count: int, language: str = "English") -> tuple[int, float]:
    """(max_tokens, timeout_seconds) sized to what this specific call needs to
    produce, so short jobs finish fast and long ones get enough room/time.
    Gujarati/Hindi need noticeably more tokens per question than English, so
    they get a per-language token budget and their own base timeout."""
    lang_key = language.strip().lower()
    script_factor = 1.7 if lang_key in {"gujarati", "hindi"} else 1.0
    base_timeout = LANG_TIMEOUT_BASE.get(lang_key, LANG_TIMEOUT_BASE["english"])
    if resource_type == "Notes":
        # Bigger first-shot budget so a full-depth Notes chapter is not
        # truncated at the start; the retry path still grows it further if needed.
        return int(8500 * script_factor), base_timeout + 200.0
    if resource_type in {"Quick-Revision", "Flashcards", "Answer-Writing", "Formula-Sheet"}:
        return int(2200 * script_factor), base_timeout + 60.0
    tokens_per_q = LANG_TOKENS_PER_Q.get(lang_key, LANG_TOKENS_PER_Q["english"])
    tokens = max(1500, min(9000, count * tokens_per_q))
    timeout = max(base_timeout, min(240.0, base_timeout + count * 8))
    return tokens, timeout


def build_user_prompt(row: sqlite3.Row, blueprint_data: dict[str, Any], source: str, requested_count: int, extra: str = "") -> str:
    glossary = f"\n{GUJARATI_GLOSSARY}\n" if row["language"].strip().lower() == "gujarati" else ""
    return f"""
Exam: {row["exam"]}
Subject: {row["subject"]}
Topic: {row["topic"]}
Language: {row["language"]}
Resource type: {resource_label(row["resource_type"])}
Requested question count: {requested_count or "not applicable"}
Requested style: {row["style"] or "clear, structured, exam-focused"}
Exam blueprint reference: {json_text(blueprint_data)}
Source material (use as primary source when present):
{source or "No source file supplied."}
{glossary}
Create content only for this topic. For PYQ, the source file is authoritative; when it is absent,
the title/content must clearly say PYQ-STYLE PRACTICE and must not claim a real year.
For tests, return as many genuinely distinct questions as safely possible; do not repeat or paraphrase.
{extra}
"""


async def generate_questions_in_chunks(
    ai: AIClient, row: sqlite3.Row, blueprint_data: dict[str, Any], source: str, total_count: int
) -> dict[str, Any]:
    """Generate a large question set (e.g. a 180-question NEET Full-Mock) as
    several smaller AI calls instead of one giant request. This is far more
    reliable — a single small chunk failing (or coming back token-starved,
    with empty options/answers) doesn't lose the whole file, and each call is
    small enough to finish well inside its timeout."""
    all_questions: list[dict[str, Any]] = []
    seen_norms: set[str] = set()
    title = instructions = None
    duration_minutes = None

    async def run_chunk(this_count: int, chunk_label: str) -> list[dict[str, Any]]:
        nonlocal title, instructions, duration_minutes
        max_tokens, timeout_seconds = estimate_generation_params(row["resource_type"], this_count, row["language"])
        system = GENERATOR_SYSTEM + "\nRequired JSON shape: " + schema_for(row["resource_type"], this_count)
        user = build_user_prompt(
            row, blueprint_data, source, this_count,
            extra=(
                f"This is {chunk_label} of a {total_count}-question {resource_label(row['resource_type'])}. "
                f"Generate exactly {this_count} FULLY COMPLETE questions for THIS part only — every question must "
                f"have all 4 options and a correct answer filled in, never leave a question half-written. Cover "
                f"different sub-aspects of the topic than the other parts would — spread coverage across the whole "
                f"topic, don't just repeat the most obvious questions in every part."
            ),
        )
        data = await ai.complete_json(
            system, user, temperature=question_temperature(row["language"]),
            max_tokens=max_tokens, timeout_seconds=timeout_seconds,
        )
        if title is None:
            title = data.get("title")
            instructions = data.get("instructions")
            duration_minutes = data.get("duration_minutes")
        return [q for q in (data.get("questions") or []) if is_complete_question(q)]

    def absorb(questions: list[dict[str, Any]]) -> int:
        added = 0
        for question in questions:
            normalized = normalize_question(str(question.get("question", "")))
            if normalized and normalized in seen_norms:
                continue
            if normalized:
                seen_norms.add(normalized)
            all_questions.append(question)
            added += 1
        return added

    chunk_size = question_chunk_size(row["language"])
    remaining = total_count
    chunk_number = 0
    while remaining > 0 and chunk_number < 80:  # hard safety cap on call count
        chunk_number += 1
        this_count = min(chunk_size, remaining)
        try:
            complete = await run_chunk(this_count, f"part {chunk_number}")
            if not complete:
                # token-starved / empty chunk — one retry before giving up on it
                complete = await run_chunk(this_count, f"part {chunk_number} (retry — the previous attempt was incomplete)")
        except AIError:
            if all_questions:
                break  # keep whatever generated fine so far instead of failing the whole file
            raise
        absorb(complete)
        remaining -= this_count

    # Top up if chunks under-delivered (e.g. several returned fewer complete
    # questions than asked), instead of silently shipping a short test.
    topup_attempts = 0
    while len(all_questions) < total_count and topup_attempts < 6:
        topup_attempts += 1
        shortfall = min(chunk_size, total_count - len(all_questions))
        try:
            absorb(await run_chunk(shortfall, "a top-up part"))
        except AIError:
            break

    return {
        "title": title or row["topic"],
        "instructions": instructions or "Attempt each question before checking the explanation.",
        "duration_minutes": duration_minutes or max(30, total_count),
        "questions": all_questions[:total_count] if len(all_questions) > total_count else all_questions,
    }


async def generate_full_syllabus_mock(
    ai: AIClient, row: sqlite3.Row, blueprint_data: dict[str, Any], source: str, total_count: int
) -> dict[str, Any]:
    """Full-Syllabus-Mock is the one resource type that is NOT scoped to a
    single topic. It spans every subject of the exam in the exam's real
    official proportion (e.g. NEET: Physics 45 / Chemistry 45 / Biology 90 =
    180) — every other test type (Chapter-Test, Full-Mock, etc.) stays
    topic/chapter-scoped and is untouched by this."""
    distribution: dict[str, int] = blueprint_data.get("subject_distribution") or {}
    if not distribution:
        # This exam has no verified subject split configured — fall back to
        # a normal single-subject test instead of guessing a split.
        return await generate_questions_in_chunks(ai, row, blueprint_data, source, total_count)
    all_questions: list[dict[str, Any]] = []
    for subject, count in distribution.items():
        if count <= 0:
            continue
        # A plain dict works everywhere `row` is used here (build_user_prompt,
        # generate_questions_in_chunks) because they only ever do row["key"]
        # lookups, exactly like sqlite3.Row supports.
        subject_row = dict(row)
        subject_row["subject"] = subject
        subject_row["topic"] = f"Entire {subject} syllabus for {row['exam']} (all chapters) — mock test set"
        subject_data = await generate_questions_in_chunks(ai, subject_row, blueprint_data, source, count)
        subject_questions = (subject_data.get("questions") or [])[:count]
        for question in subject_questions:
            question["subject_tag"] = subject
        all_questions.extend(subject_questions)
    return {
        "title": f"{row['exam']} Full Syllabus Mock Test",
        "instructions": "Full-length mock covering the ENTIRE syllabus across every subject, in the exam's official proportion. Attempt every question before checking the answer.",
        "duration_minutes": max(60, sum(distribution.values())),
        "questions": all_questions,
    }


async def generate_resource(ai: AIClient, db: Database, row: sqlite3.Row) -> str:
    source = await extract_source(row["source_path"])
    resource_type = row["resource_type"]
    is_question_resource = resource_type in QUESTION_RESOURCE_TYPES
    requested_count = int(row["question_count"] or DEFAULT_QUESTION_COUNT) if is_question_resource else 0
    blueprint_data = EXAM_CONFIG.get(row["exam"], {})

    if resource_type == "Full-Syllabus-Mock":
        data = await generate_full_syllabus_mock(ai, row, blueprint_data, source, requested_count)
    elif is_question_resource and requested_count > question_chunk_size(row["language"]):
        data = await generate_questions_in_chunks(ai, row, blueprint_data, source, requested_count)
    else:
        max_tokens, timeout_seconds = estimate_generation_params(resource_type, requested_count, row["language"])
        system = GENERATOR_SYSTEM + "\nRequired JSON shape: " + schema_for(resource_type, requested_count)
        user = build_user_prompt(row, blueprint_data, source, requested_count)
        data = await ai.complete_json(
            system, user, temperature=question_temperature(row["language"]) if is_question_resource else 0.35,
            max_tokens=max_tokens, timeout_seconds=timeout_seconds,
        )
        if is_question_resource:
            data = keep_complete_questions(data)

    validate_content(data, resource_type)
    data = await filter_unique_questions(db, row, data, ai)
    if is_question_resource and not data.get("questions"):
        raise AIError("All generated questions were duplicates; job rejected safely.", retryable=True)
    if resource_type == "PYQ" and not source:
        data["title"] = f"PYQ-STYLE PRACTICE — {data['title']}"
    return build_html(data, row)


# ============================================================================ #
# BOT STATE, ACCESS CONTROL, QUEUE, AND PROGRESS
# ============================================================================ #


@dataclass
class BatchState:
    batch_id: str
    chat_id: int
    started_at: float = field(default_factory=time.monotonic)
    stopped: asyncio.Event = field(default_factory=asyncio.Event)
    progress_message_id: Optional[int] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_progress: float = 0.0
    dashboard: bool = False
    exam_names: list[str] = field(default_factory=list)


@dataclass
class FactoryState:
    db: Database
    ai: AIClient
    queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    batches: dict[str, BatchState] = field(default_factory=dict)
    contexts: dict[int, dict[str, Any]] = field(default_factory=dict)
    workers: list[asyncio.Task[Any]] = field(default_factory=list)
    source_paths: dict[int, str] = field(default_factory=dict)
    source_text_names: dict[int, str] = field(default_factory=dict)


STATE: Optional[FactoryState] = None


def state() -> FactoryState:
    if STATE is None:
        raise RuntimeError("Factory state is not initialized")
    return STATE


async def allowed(update: Update) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False
    if user.id in OWNER_IDS:
        return True
    if chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return await state().db.is_group_allowed(chat.id)
    return await state().db.is_user_allowed(user.id)


async def owner_only(update: Update) -> bool:
    user = update.effective_user
    if not user or user.id not in OWNER_IDS:
        if update.effective_message:
            await update.effective_message.reply_text("Access denied. This command is owner-only.")
        return False
    return True


async def deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("Access denied. Ask the owner to authorize this user or group.")


async def require_access(update: Update) -> bool:
    if await allowed(update):
        return True
    await deny(update)
    return False


def exam_keyboard() -> InlineKeyboardMarkup:
    names = list(EXAM_CONFIG)
    rows = [[InlineKeyboardButton(name, callback_data=f"exam:{index}")] for index, name in enumerate(names)]
    return InlineKeyboardMarkup(rows)


def language_keyboard(exam: str) -> InlineKeyboardMarkup:
    languages = EXAM_CONFIG[exam]["languages"]
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(language, callback_data=f"lang:{safe_filename(exam)}:{index}")] for index, language in enumerate(languages)]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 AUTO BUILD (this exam)", callback_data="menu:auto"), InlineKeyboardButton("🎯 SELECT RESOURCES", callback_data="menu:resources")],
            [InlineKeyboardButton("🧪 TEST FACTORY", callback_data="menu:tests"), InlineKeyboardButton("🎨 CUSTOM PROMPT", callback_data="menu:prompt")],
            [InlineKeyboardButton("📄 SOURCE → HTML", callback_data="menu:source"), InlineKeyboardButton("📊 JOB STATUS", callback_data="menu:status")],
            [InlineKeyboardButton("▶ RESUME JOBS", callback_data="menu:resume"), InlineKeyboardButton("🔁 RETRY FAILED", callback_data="menu:retry")],
            [InlineKeyboardButton("🛑 STOP JOB", callback_data="menu:stop"), InlineKeyboardButton("📦 CREATE ZIP", callback_data="menu:zip")],
            [InlineKeyboardButton("🏠 REBUILD ACADEMY HUBS", callback_data="menu:hub")],
            [InlineKeyboardButton("⚙️ ENGINE TOOLS", callback_data="menu:eng")],
        ]
    )


def engine_keyboard() -> InlineKeyboardMarkup:
    """Advanced engine controls: scoped builds, resume/repair, validate/audit."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 AUTO BUILD THIS EXAM", callback_data="menu:auto")],
            [InlineKeyboardButton("📋 BUILD ONE EXAM", callback_data="eng:pick"), InlineKeyboardButton("🧨 ALL EXAMS (advanced)", callback_data="eng:alllang")],
            [InlineKeyboardButton("🔁 REBUILD FAILED", callback_data="eng:failed"), InlineKeyboardButton("▶ RESUME AUTO BUILD", callback_data="eng:resume")],
            [InlineKeyboardButton("🧾 VALIDATE ALL", callback_data="eng:validate"), InlineKeyboardButton("🧪 AUDIT ALL", callback_data="eng:audit")],
            [InlineKeyboardButton("🏠 REBUILD ACADEMY HUBS", callback_data="menu:hub")],
            [InlineKeyboardButton("◀ MAIN MENU", callback_data="eng:back")],
        ]
    )


def exam_picker_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, name in enumerate(EXAM_CONFIG):
        if index % 2 == 0:
            rows.append([])
        rows[-1].append(InlineKeyboardButton(name, callback_data=f"pickexam:{index}"))
    rows.append([InlineKeyboardButton("◀ ENGINE TOOLS", callback_data="menu:eng")])
    return InlineKeyboardMarkup(rows)


def built_exams() -> list[str]:
    """Exams that currently have at least one generated HTML file on disk."""
    return [exam for exam in EXAM_CONFIG if exam_html_files(exam)]


def zip_options_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    current = state().contexts.get(chat_id, {})
    exam = current.get("exam")
    rows: list[list[InlineKeyboardButton]] = []
    if exam and exam in EXAM_CONFIG and exam_html_files(exam):
        rows.append([InlineKeyboardButton(f"📦 ZIP {exam} only ({len(exam_html_files(exam))} files)", callback_data="zipopt:exam")])
    rows.append([InlineKeyboardButton("🗂 ALL EXAMS — one ZIP per exam", callback_data="zipopt:all")])
    rows.append([InlineKeyboardButton("📦 Everything — single ZIP", callback_data="zipopt:single")])
    rows.append([InlineKeyboardButton("🏠 Rebuild academy hubs", callback_data="menu:hub")])
    return InlineKeyboardMarkup(rows)


async def send_blueprint(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = state().contexts.get(chat_id, {})
    exam = current.get("exam")
    language = current.get("language")
    if not exam or not language:
        return
    config = EXAM_CONFIG[exam]
    subjects = "\n".join(f"• {html.escape(subject)}" for subject in config["subjects"])
    resources = "\n".join(f"• {html.escape(resource_label(resource))}" for resource in config["recommended_resources"])
    text = (
        "🤖 <b>EXAM BLUEPRINT</b>\n\n"
        f"<b>Exam:</b> {html.escape(exam)}\n<b>Language:</b> {html.escape(language)}\n\n"
        f"<b>Subjects</b>\n{subjects}\n\n"
        f"<b>Paper pattern:</b> {html.escape(str(config['exam_pattern']))}\n\n"
        f"<b>Recommended resources</b>\n{resources}\n\n"
        "<i>Only information you add to EXAM_CONFIG is treated as configured official information.</i>"
    )
    await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=main_menu_keyboard())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    chat_id = update.effective_chat.id
    state().contexts[chat_id] = {}
    await update.effective_message.reply_text(
        "⚡ SONIC RESOURCE FACTORY\n\nWelcome to your AI Educational Content Factory.\n\n🎯 Select Exam",
        reply_markup=exam_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    await update.effective_message.reply_text(
        "⚡ PREPGRID AUTO BUILD ENGINE\n\n"
        "/start — select your exam and its language\n"
        "AUTO BUILD (menu) — builds that ONE selected exam A→Z (notes, quick\n"
        "revision, flashcards, practice, tests, full mock — the full syllabus, one\n"
        "language) and auto-sends its ZIP when done. Never builds several exams at once\n"
        "Engine Tools → BUILD ONE EXAM / 🧨 ALL EXAMS (advanced) / VALIDATE / AUDIT\n"
        "/reset — clear ALL running/pending builds across every exam so nothing keeps reappearing\n"
        "/prompt — natural-language generation request\n"
        "/status — current batch status\n"
        "/jobs — recent jobs\n"
        "/resume — resume pending jobs after a restart/crash\n"
        "/cancelpending — discard pending/failed jobs without running them\n"
        "/retry — retry failed jobs\n"
        "/audit or /validate — offline validation + manifest sweep over all exams\n"
        "/zip — pack the library: one ZIP per exam (every file made so far, plus its hub page)\n"
        "/stop or /cancel — stop new work safely\n"
        "/adduser USER_ID — owner: authorize a user\n"
        "/removeuser USER_ID — owner: remove a user\n"
        "/users — owner: list users\n"
        "/addgrup — owner: authorize this group\n"
        "/removegrup — owner: remove this group\n"
        "/groups — owner: list groups\n\n"
        "Menu → ⚙️ ENGINE TOOLS for BUILD ONE EXAM, REBUILD FAILED, RESUME,\n"
        "VALIDATE ALL and AUDIT ALL. Send /prompt with fields such as Exam,\n"
        "Language, Resource, Scope, Questions, Difficulty, and Style."
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_access(update):
        return
    chat_id = query.message.chat_id
    data = query.data or ""
    if data.startswith("exam:"):
        index = int(data.split(":", 1)[1])
        exam = list(EXAM_CONFIG)[index]
        state().contexts[chat_id] = {"exam": exam}
        await query.edit_message_text(
            f"Exam selected: {exam}\n\n🌐 SELECT LANGUAGE\n"
            f"🤖 Recommended Language: {EXAM_CONFIG[exam]['recommended_language']}",
            reply_markup=language_keyboard(exam),
        )
        return
    if data.startswith("lang:"):
        _, encoded_exam, language_index = data.split(":")
        exam = next((name for name in EXAM_CONFIG if safe_filename(name) == encoded_exam), None)
        if not exam:
            await query.edit_message_text("Exam selection expired. Please use /start again.")
            return
        language = EXAM_CONFIG[exam]["languages"][int(language_index)]
        state().contexts[chat_id] = {"exam": exam, "language": language}
        await query.edit_message_text(f"Exam: {exam}\nLanguage: {language}\n\nLoading blueprint…")
        await send_blueprint(chat_id, context)
        return
    if data.startswith("menu:"):
        await menu_action(chat_id, data.split(":", 1)[1], context, query)


async def menu_action(chat_id: int, action: str, context: ContextTypes.DEFAULT_TYPE, query: Any = None) -> None:
    current = state().contexts.get(chat_id, {})
    if action == "auto":
        exam = current.get("exam")
        if exam and exam in EXAM_CONFIG:
            language = current.get("language") or EXAM_CONFIG[exam].get("recommended_language") or "English"
            await auto_build_exam_for_chat(chat_id, context, exam, language)
        else:
            await context.bot.send_message(
                chat_id,
                "🚀 <b>AUTO BUILD</b>\n\n"
                "Pick the exam you want built first — AUTO BUILD then makes that "
                "<b>ONE</b> exam's complete syllabus (notes, quick revision, flashcards, "
                "practice, tests, full mock) end-to-end and hands you the ZIP at the end. "
                "It never builds several exams at once.",
                parse_mode="HTML",
                reply_markup=exam_picker_keyboard(),
            )
    elif action == "eng":
        await context.bot.send_message(
            chat_id,
            "⚙️ <b>ENGINE TOOLS</b>\n\n"
            "Full-exam engine builds, resume/repair, validation and audit. "
            "AUTO BUILD ALL reads every exam from EXAM_CONFIG automatically.",
            parse_mode="HTML",
            reply_markup=engine_keyboard(),
        )
    elif action == "resources":
        exam = current.get("exam")
        if not exam:
            await context.bot.send_message(chat_id, "Use /start first.")
            return
        resources = EXAM_CONFIG[exam]["recommended_resources"]
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(resource_label(resource), callback_data=f"resource:{resource}")] for resource in resources]
            + [[InlineKeyboardButton("Build selected", callback_data="resource:__done")]]
        )
        state().contexts[chat_id]["selecting_resources"] = []
        await context.bot.send_message(chat_id, "Select resources, then press Build selected.", reply_markup=keyboard)
    elif action == "tests":
        await context.bot.send_message(chat_id, "Test Factory\n\nUse /prompt for a custom test, or select an exam first and choose AUTO BUILD ALL.", reply_markup=main_menu_keyboard())
    elif action == "prompt":
        state().contexts.setdefault(chat_id, {})["awaiting_prompt"] = True
        await context.bot.send_message(chat_id, "Send your generation request. Example:\n\nExam: NEET\nLanguage: Gujarati\nResource: Notes\nScope: All Biology topics\nStyle: NCERT based\nOutput: Separate HTML per topic")
    elif action == "source":
        state().contexts.setdefault(chat_id, {})["awaiting_source"] = True
        await context.bot.send_message(chat_id, "Send a PDF or TXT source file. I will ask which resource type to build from it.")
    elif action == "status":
        await status_command_for_chat(chat_id, context)
    elif action == "resume":
        await resume_for_chat(chat_id, context)
    elif action == "retry":
        await retry_for_chat(chat_id, context)
    elif action == "stop":
        await stop_for_chat(chat_id, context)
    elif action == "zip":
        await create_zip_for_chat(chat_id, context)
    elif action == "hub":
        await rebuild_hubs_for_chat(chat_id, context)


async def audit_report_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """VALIDATE ALL / AUDIT ALL — offline manifest + validation sweep over every
    exam. Reads and validates the whole OUTPUT library; never generates."""
    await context.bot.send_chat_action(chat_id, action="typing")
    try:
        audit = await asyncio.to_thread(audit_all_exams)
    except Exception:
        logger.exception("Audit sweep failed")
        await context.bot.send_message(chat_id, "Audit failed — see logs. It may be mid-write; run again after the current build settles.")
        return
    complete = audit["exams_complete"]
    total = audit["exams_total"]
    lines = [f"🧪 <b>ACADEMY AUDIT</b>\n\nExams: <b>{complete}/{total}</b> fully complete"]
    lines.append(
        f"Resources: {audit['resources_generated']} generated · {audit['resources_validated']} validated · "
        f"{audit['resources_failed']} failed"
    )
    lines.append(
        f"Missing: {audit['missing_total']} · Broken links: {audit['broken_total']} · Duplicates: {audit['duplicates_total']}"
    )
    for exam, report in audit["reports"].items():
        mark = "✅" if report["status"] == "COMPLETE" else ("⚠️" if report["status"] == "REVIEW_REQUIRED" else "⏳")
        lines.append(f"{mark} {html.escape(exam)} — {report['validated']}/{report['generated']} valid, {report['missing']} missing")
    status_line = (
        "🏆 <b>ALL EXAMS 101% PREPARATION READY</b>"
        if complete == total
        else "⚠️ <b>REVIEW REQUIRED</b> — use AUTO BUILD ALL to repair, then audit again."
    )
    await context.bot.send_message(chat_id, "\n".join(lines) + f"\n\n{status_line}", parse_mode="HTML")


async def eng_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not await require_access(update):
        return
    await query.answer()
    chat_id = query.message.chat_id
    action = (query.data or "").split(":", 1)[1]
    if action == "back":
        await context.bot.send_message(chat_id, "⚡ PREPGRID — main menu", reply_markup=main_menu_keyboard())
    elif action == "alllang":
        await auto_build_gate_all(chat_id, context)
    elif action == "pick":
        await context.bot.send_message(chat_id, "📋 Choose an exam to AUTO BUILD (full plan at correct resource levels):", reply_markup=exam_picker_keyboard())
    elif action == "failed":
        await retry_for_chat(chat_id, context)
        await context.bot.send_message(chat_id, "Engine ready.", reply_markup=engine_keyboard())
    elif action == "resume":
        await resume_for_chat(chat_id, context)
        await context.bot.send_message(chat_id, "Engine ready.", reply_markup=engine_keyboard())
    elif action == "validate":
        await audit_report_for_chat(chat_id, context)
    elif action == "audit":
        await audit_report_for_chat(chat_id, context)


def all_build_language_keyboard() -> InlineKeyboardMarkup:
    """Language gate for AUTO BUILD ALL — every distinct medium across exams,
    plus the per-exam recommended option. Building always happens in ONE medium,
    never across several languages at once."""
    rows = [[InlineKeyboardButton(f"🌐 {medium}", callback_data=f"autolang:all:{medium}")]
            for medium in union_languages()]
    rows.append([InlineKeyboardButton("⚙️ Recommended per exam (auto)", callback_data="autolang:all:__auto__")])
    rows.append([InlineKeyboardButton("◀ ENGINE TOOLS", callback_data="menu:eng")])
    return InlineKeyboardMarkup(rows)


def exam_build_language_keyboard(exam: str) -> InlineKeyboardMarkup:
    """Language gate for BUILD ONE EXAM — the exam's supported media plus its
    recommended default. The whole exam is then built in that single language."""
    blueprint_data = EXAM_CONFIG[exam]
    recommended = blueprint_data.get("recommended_language") or "English"
    rows = [[InlineKeyboardButton(f"⚙️ Recommended ({recommended})", callback_data="autolang:one:__auto__")]]
    rows += [
        [InlineKeyboardButton(f"🌐 {medium}", callback_data=f"autolang:one:{medium}")]
        for medium in blueprint_data.get("languages") or []
        if medium != recommended
    ]
    rows.append([InlineKeyboardButton("◀ EXAM PICKER", callback_data="eng:pick")])
    return InlineKeyboardMarkup(rows)


def union_languages() -> list[str]:
    """Distinct media offered across all configured exams, in first-seen order."""
    media: list[str] = []
    for exam in EXAM_CONFIG:
        for medium in EXAM_CONFIG[exam].get("languages") or []:
            if medium not in media:
                media.append(medium)
    return media


async def auto_build_gate_all(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id,
        "🚀 <b>PREPGRID AUTO BUILD ALL</b>\n\n"
        "Pick <b>ONE</b> medium first. The engine builds every exam that offers "
        "that language in that single language and skips the rest — it never "
        "builds several languages at once. Choose 'Recommended per exam' to "
        "build each exam in its own default medium.",
        parse_mode="HTML",
        reply_markup=all_build_language_keyboard(),
    )


async def auto_build_gate_exam(chat_id: int, context: ContextTypes.DEFAULT_TYPE, exam: str) -> None:
    await context.bot.send_message(
        chat_id,
        f"📘 <b>AUTO BUILD: {html.escape(exam)}</b>\n\n"
        "Pick the medium — the whole exam (every subject, chapter and resource) "
        "is built in that <b>ONE</b> language.",
        parse_mode="HTML",
        reply_markup=exam_build_language_keyboard(exam),
    )


async def autolang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not await require_access(update):
        return
    await query.answer()
    chat_id = query.message.chat_id
    parts = (query.data or "").split(":", 2)
    if len(parts) < 3:
        return
    mode, value = parts[1], parts[2]
    if mode == "all":
        if value == "__auto__":
            await auto_build_all_for_chat(chat_id, context)
        else:
            await auto_build_all_for_chat(chat_id, context, language=value)
        return
    # mode == "one": single-exam build in the chosen medium
    exam = state().contexts.get(chat_id, {}).get("exam")
    if not exam or exam not in EXAM_CONFIG:
        await query.edit_message_text("Exam selection expired. Use /start again.")
        return
    if value == "__auto__":
        language = EXAM_CONFIG[exam].get("recommended_language") or "English"
    elif value not in (EXAM_CONFIG[exam].get("languages") or []):
        await query.edit_message_text(f"{value} is not offered for {exam}. Pick one of its languages.")
        return
    else:
        language = value
    await query.edit_message_text(f"▶ Building {exam} in {language} — full resource plan queued.")
    await auto_build_exam_for_chat(chat_id, context, exam, language)


async def pick_exam_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not await require_access(update):
        return
    await query.answer()
    chat_id = query.message.chat_id
    index = int((query.data or "pickexam:0").split(":", 1)[1])
    exam = list(EXAM_CONFIG)[index]
    state().contexts.setdefault(chat_id, {})["exam"] = exam
    await auto_build_gate_exam(chat_id, context, exam)


async def resource_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not await require_access(update):
        return
    await query.answer()
    chat_id = query.message.chat_id
    choice = (query.data or "").split(":", 1)[1]
    current = state().contexts.setdefault(chat_id, {})
    if choice == "__done":
        selected = current.get("selecting_resources") or EXAM_CONFIG[current.get("exam", "NEET")]["recommended_resources"]
        await create_auto_batch(chat_id, context, selected)
        return
    selected = current.setdefault("selecting_resources", [])
    if choice in selected:
        selected.remove(choice)
    else:
        selected.append(choice)
    await query.edit_message_reply_markup(
        InlineKeyboardMarkup(
            [[InlineKeyboardButton(("✓ " if resource in selected else "") + resource_label(resource), callback_data=f"resource:{resource}")] for resource in EXAM_CONFIG[current["exam"]]["recommended_resources"]]
            + [[InlineKeyboardButton(f"Build selected ({len(selected)})", callback_data="resource:__done")]]
        )
    )


async def create_auto_batch(chat_id: int, context: ContextTypes.DEFAULT_TYPE, selected_resources: Optional[list[str]] = None) -> None:
    """Single-exam AUTO BUILD (also used by the resource selector). The engine
    plans the chosen exam at the correct resource levels (unit/subject/exam)."""
    current = state().contexts.get(chat_id, {})
    exam = current.get("exam")
    if not exam or exam not in EXAM_CONFIG:
        await context.bot.send_message(chat_id, "Use /start to select an exam first.")
        return
    language = current.get("language") or EXAM_CONFIG[exam].get("recommended_language") or "English"
    await auto_build_exam_for_chat(chat_id, context, exam, language, selected_resources)


async def auto_build_exam_for_chat(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    exam: str,
    language: Optional[str] = None,
    resources: Optional[list[str]] = None,
) -> None:
    """Plan + queue one exam through the resource planner."""
    if exam not in EXAM_CONFIG:
        await context.bot.send_message(chat_id, f"Exam '{exam}' is not in EXAM_CONFIG.")
        return
    blueprint_data = EXAM_CONFIG[exam]
    language = language or blueprint_data.get("recommended_language") or "English"
    specs = missing_plan_jobs(exam, language, resources=resources)
    total_required = len(plan_exam_build(exam, language, resources=resources))
    if not specs:
        await context.bot.send_message(chat_id, f"{exam}: all {total_required} planned resources already exist and pass validation. Use /audit to inspect coverage.")
        return
    if not specs:
        await context.bot.send_message(
            chat_id,
            f"No buildable resources for {exam}. Add resource types with builders to EXAM_CONFIG, "
            "or pick supported resources from the menu.",
        )
        return
    batch_id = uuid.uuid4().hex
    jobs = _stamp_jobs(specs, batch_id, chat_id, exam, language, None, "exam-focused")
    await state().db.add_build(batch_id, chat_id, "auto-exam", [exam])
    await _launch_batch(
        chat_id, context, jobs,
        started_text=f"🚀 <b>AUTO BUILD:</b> {html.escape(exam)} — {len(jobs)} resource(s) queued ({html.escape(language)}).",
        dashboard=True, exams=[exam],
    )


async def auto_build_all_for_chat(
    chat_id: int, context: ContextTypes.DEFAULT_TYPE, language: Optional[str] = None
) -> None:
    """AUTO BUILD ALL — dynamically reads EVERY exam in EXAM_CONFIG (never a
    hard-coded list). Any exam added to EXAM_CONFIG later is included
    automatically on the next run.

    `language` is the AUTO-BUILD language gate: pass one medium and only exams
    that actually offer it are built (in that single language); exams that do
    not list it are skipped and reported. `language=None` = each exam builds in
    its own recommended medium. The engine never builds an exam in several
    languages at once."""
    exams = list(EXAM_CONFIG)
    if not exams:
        await context.bot.send_message(chat_id, "EXAM_CONFIG is empty — add exams first.")
        return
    batch_id = uuid.uuid4().hex
    jobs: list[dict[str, Any]] = []
    planned_exams: list[str] = []
    skipped_exams: list[str] = []
    for exam in exams:
        blueprint_data = EXAM_CONFIG[exam]
        if language:
            if language not in (blueprint_data.get("languages") or []):
                skipped_exams.append(exam)
                continue
            chosen_language = language
        else:
            chosen_language = blueprint_data.get("recommended_language") or "English"
        specs = plan_exam_build(exam, chosen_language)
        if not specs:
            skipped_exams.append(exam)
            continue
        jobs.extend(_stamp_jobs(specs, batch_id, chat_id, exam, chosen_language, None, "exam-focused"))
        planned_exams.append(exam)
    if not jobs:
        await context.bot.send_message(chat_id, "No buildable jobs across any exam. Check EXAM_CONFIG.")
        return
    if language:
        header = f"🚀 <b>PREPGRID AUTO BUILD ALL — {html.escape(language)}</b>"
        note = f"Exams built: <b>{len(planned_exams)}</b> · Resources queued: <b>{len(jobs)}</b>"
        if skipped_exams:
            note += f"\nSkipped (no {html.escape(language)} medium): {', '.join(html.escape(e) for e in skipped_exams)}"
    else:
        header = "🚀 <b>PREPGRID AUTO BUILD ALL</b>"
        note = f"Exams: <b>{len(planned_exams)}</b> · Resources queued: <b>{len(jobs)}</b>"
    await state().db.add_build(batch_id, chat_id, "auto-all", planned_exams)
    await _launch_batch(
        chat_id, context, jobs,
        started_text=f"{header}\n{note}\n"
        "Progress dashboard is live above — every valid HTML file is uploaded as it is built.",
        dashboard=True, exams=planned_exams,
    )


def parse_prompt(raw: str, chat_id: int) -> dict[str, Any]:
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().casefold()] = value.strip()
    exam_value = fields.get("exam", "")
    exam = next((name for name in EXAM_CONFIG if name.casefold() == exam_value.casefold()), None)
    if not exam:
        exam = next((name for name in EXAM_CONFIG if name.casefold() in raw.casefold()), None)
    if not exam:
        exam = state().contexts.get(chat_id, {}).get("exam")
    if not exam:
        raise ValueError("Please include an exam, for example: Exam: NEET")
    language = fields.get("language") or EXAM_CONFIG[exam]["recommended_language"]
    language = next((lang for lang in EXAM_CONFIG[exam]["languages"] if lang.casefold() == language.casefold()), language)
    resource_raw = fields.get("resource", "Notes").casefold()
    aliases = {
        "quick revision": "Quick-Revision", "quick-revision": "Quick-Revision", "topic test": "Topic-Test",
        "chapter test": "Chapter-Test", "subject test": "Subject-Test", "full mock": "Full-Mock",
        "test": "Topic-Test", "pyq": "PYQ", "practice": "Practice", "flashcards": "Flashcards",
        "current affairs": "Current-Affairs", "answer writing": "Answer-Writing",
    }
    resource = aliases.get(resource_raw, next((r for r in EXAM_CONFIG[exam]["recommended_resources"] if r.casefold() == resource_raw), "Notes"))
    scope = fields.get("scope", "All syllabus topics")
    subject = fields.get("subject")
    if subject and subject.casefold() not in {s.casefold() for s in EXAM_CONFIG[exam]["subjects"]}:
        subject = None
    topics = extract_topics(scope, exam, subject)
    count_raw = fields.get("questions", fields.get("count", ""))
    count = parse_number(count_raw, -1) if count_raw.strip() else None
    if count == -1:
        count = None
    style = fields.get("style", fields.get("difficulty", "exam-focused"))
    return {"exam": exam, "language": language, "resource": resource, "topics": topics, "count": count, "style": style}


async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    chat_id = update.effective_chat.id
    raw = " ".join(context.args).strip() if context.args else ""
    if not raw:
        state().contexts.setdefault(chat_id, {})["awaiting_prompt"] = True
        await update.effective_message.reply_text("Send your custom prompt with Exam, Language, Resource, and Scope fields.")
        return
    await handle_prompt_text(chat_id, raw, context)


async def handle_prompt_text(chat_id: int, raw: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        request = parse_prompt(raw, chat_id)
    except ValueError as exc:
        await context.bot.send_message(chat_id, str(exc))
        return
    state().contexts.setdefault(chat_id, {}).update({"exam": request["exam"], "language": request["language"], "awaiting_prompt": False})
    await start_batch(chat_id, context, request["exam"], request["language"], request["topics"], [request["resource"]], request["count"], request["style"])


async def _launch_batch(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    jobs: list[dict[str, Any]],
    started_text: Optional[str] = None,
    dashboard: bool = False,
    exams: Optional[list[str]] = None,
) -> BatchState:
    """Shared batch launcher used by single-exam builds and AUTO BUILD ALL.
    Creates the batch, persists every job, enqueues them and shows a live
    progress message (plain progress bar, or the all-exams dashboard)."""
    batch_id = uuid.uuid4().hex
    batch = BatchState(batch_id=batch_id, chat_id=chat_id)
    if dashboard:
        batch.dashboard = True
        batch.exam_names = list(exams or [])
    state().batches[batch_id] = batch
    await state().db.add_jobs(jobs)
    for job in jobs:
        await state().queue.put(job["job_id"])
    counts = {"PENDING": len(jobs)}
    text = (dashboard_text(batch, counts, {}, "") if dashboard
            else progress_text(batch, len(jobs), 0, 0, 0, "Queued"))
    progress = await context.bot.send_message(chat_id, text, parse_mode="HTML")
    batch.progress_message_id = progress.message_id
    await update_progress(batch, context, force=True)
    if started_text:
        await context.bot.send_message(chat_id, started_text, reply_markup=main_menu_keyboard())
    return batch


def _stamp_jobs(
    jobs: list[dict[str, Any]],
    batch_id: str,
    chat_id: int,
    exam: str,
    language: str,
    question_count: Optional[int],
    style: str,
) -> list[dict[str, Any]]:
    """Attach runtime identity (ids, chat, language, source, counts) to planner
    job specs so they match the schema `Database.add_jobs` expects."""
    stamped: list[dict[str, Any]] = []
    for job in jobs:
        row = dict(job)
        row.update({
            "job_id": uuid.uuid4().hex,
            "batch_id": batch_id,
            "chat_id": chat_id,
            "owner_id": chat_id,
            "exam": exam,
            "language": language,
            "created_at": now_iso(),
            "source_path": state().source_paths.get(chat_id),
            "question_count": resolve_question_count(exam, job["resource_type"], question_count),
            "style": style,
        })
        stamped.append(row)
    return stamped


async def start_batch(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    exam: str,
    language: str,
    topics: list[tuple[str, str]],
    resources: list[str],
    question_count: Optional[int] = None,
    style: str = "exam-focused",
) -> None:
    """Custom-scope generation (used by /prompt and selected-topic flows):
    builds exactly topics x resources as the user asked, no scope re-planning."""
    jobs: list[dict[str, Any]] = []
    for subject, topic in topics:
        for resource in resources:
            jobs.append(
                {
                    "subject": subject,
                    "topic": topic,
                    "chapter": "Configured topic",
                    "resource_type": resource,
                    "question_count": resolve_question_count(exam, resource, question_count),
                }
            )
    batch = await _launch_batch(
        chat_id, context, _stamp_jobs(jobs, uuid.uuid4().hex, chat_id, exam, language, question_count, style),
        started_text=f"Generation started: {len(jobs)} job(s). Each valid HTML file will be uploaded individually.",
    )


def progress_text(batch: BatchState, total: int, completed: int, running: int, failed: int, last: str) -> str:
    pending = max(0, total - completed - running - failed)
    percent = int((completed / total) * 100) if total else 100
    return (
        "⚡ <b>PREPGRID AUTO BUILD</b>\n"
        f"📚 Batch: <code>{batch.batch_id[:8]}</code>\n"
        f"{progress_bar(completed, total)} {percent}%\n"
        f"✅ Completed: {completed}/{total}\n"
        f"🔄 Running: {running}\n⏳ Pending: {pending}\n❌ Failed: {failed}\n"
        f"📤 Last uploaded: {html.escape(last or '—')}\n"
        f"⏱ Elapsed: {format_duration(time.monotonic() - batch.started_at)}"
    )


def dashboard_text(
    batch: BatchState,
    counts: dict[str, int],
    exam_counts: dict[str, dict[str, int]],
    running: str,
) -> str:
    """AUTO BUILD ALL progress dashboard — one line per exam plus the global bar
    (the same shape shown for a single-exam build, just with one exam listed)."""
    total = sum(counts.values())
    completed = int(counts.get("COMPLETED", 0))
    running_n = int(counts.get("RUNNING", 0))
    failed = int(counts.get("FAILED", 0))
    pending = max(0, total - completed - running_n - failed)
    percent = int((completed / total) * 100) if total else 100
    exam_names = getattr(batch, "exam_names", None) or list(exam_counts)
    exam_lines: list[str] = []
    shown = 0
    for exam in exam_names:
        ec = exam_counts.get(exam, {})
        c = int(ec.get("COMPLETED", 0))
        p = int(ec.get("PENDING", 0))
        r = int(ec.get("RUNNING", 0))
        f = int(ec.get("FAILED", 0))
        if not c and not p and not r and not f:
            mark, tail = "○", "queued"
        elif p == 0 and r == 0 and f == 0 and c > 0:
            mark, tail = "✅", "complete"
        elif r > 0 or p > 0:
            mark, tail = "⏳", "building"
        else:
            mark, tail = "⚠️", "review"
        if shown < 8:
            exam_lines.append(f"{mark} <b>{html.escape(exam)}</b> {c}✓ · {p}⏳ · {f}✗ <i>({tail})</i>")
        shown += 1
    if len(exam_names) > 8:
        exam_lines.append(f"<i>+{len(exam_names) - 8} more exams…</i>")
    return (
        "🚀 <b>PREPGRID AUTO BUILD ALL</b>\n"
        f"Exams: <b>{len(exam_names)}</b> · Batch: <code>{batch.batch_id[:8]}</code>\n"
        f"{progress_bar(completed, total)} <b>{percent}%</b>\n"
        f"✅ Completed: {completed} · ⏳ Building: {running_n} · Pending: {pending} · ❌ Failed: {failed}\n"
        "\n".join(exam_lines)
        + (f"\n<b>Current:</b> {html.escape(running) if running else '—'}")
        + f"\n⏱ {format_duration(time.monotonic() - batch.started_at)}"
    )


async def update_progress(batch: BatchState, context: ContextTypes.DEFAULT_TYPE, force: bool = False, last: str = "") -> None:
    if not batch.progress_message_id:
        return
    async with batch.lock:
        if not force and time.monotonic() - batch.last_progress < PROGRESS_UPDATE_SECONDS:
            return
        counts = await state().db.job_counts(batch.batch_id)
        if getattr(batch, "dashboard", False):
            exam_counts = await state().db.exam_job_counts(batch.batch_id)
            running_rows = await state().db.running_jobs(batch.batch_id, 3)
            running = " | ".join(
                f"{r['exam']} › {r['subject']} › {resource_label(r['resource_type'])}" for r in running_rows
            )
            message = dashboard_text(batch, counts, exam_counts, running)
        else:
            total = sum(counts.values())
            message = progress_text(batch, total, counts.get("COMPLETED", 0), counts.get("RUNNING", 0), counts.get("FAILED", 0), last)
        try:
            await context.bot.edit_message_text(message, chat_id=batch.chat_id, message_id=batch.progress_message_id, parse_mode="HTML")
        except Exception:
            pass
        batch.last_progress = time.monotonic()


async def worker(worker_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Worker %s started", worker_id)
    # External job attempts = 1 real attempt + auto-repair passes. Transient
    # API errors are retried INSIDE the AI client (MAX_AI_RETRIES); this outer
    # bound only lets a genuinely failed file be repaired a couple of times
    # before it is parked in the FAILED queue for the final report.
    max_external = 1 + int(BUILD_CONFIG.get("max_repairs_content", 2))
    while True:
        job_id = await state().queue.get()
        try:
            row = await state().db.get_job(job_id)
            if not row or row["status"] not in {"PENDING", "FAILED"}:
                continue
            batch = state().batches.get(row["batch_id"])
            if batch and batch.stopped.is_set():
                await state().db.set_job_pending(job_id, "Stopped before processing")
                continue
            await state().db.set_job_running(job_id)
            row = await state().db.get_job(job_id)
            if not row:
                continue
            logger.info("Job %s started", job_id[:8])
            existing = await state().db.existing_resource(row)
            if existing and existing["file_path"] and Path(existing["file_path"]).exists():
                existing_problems = validate_html_resource(
                    Path(existing["file_path"]).read_text(encoding="utf-8", errors="replace"),
                    row["resource_type"],
                )
                if not existing_problems:
                    await state().db.set_job_done(job_id, existing["file_path"])
                    if batch:
                        await update_progress(batch, context, last=Path(existing["file_path"]).name)
                    continue
                # Existing file exists but fails validation → regenerate it
                # (auto-repair of a stale/broken resource).
                logger.info("Job %s existing file invalid — regenerating", job_id[:8])
            file_text = await generate_resource(state().ai, state().db, row)
            # Output validation gate — an invalid file is never written or
            # uploaded; it goes back into the queue for auto-repair.
            problems = validate_html_resource(file_text, row["resource_type"])
            if problems:
                raise ValueError("Validation failed: " + "; ".join(problems))
            output_path = Path(OUTPUT_DIR) / safe_filename(row["exam"]) / safe_filename(row["subject"]) / safe_filename(resource_label(row["resource_type"]))
            output_path.mkdir(parents=True, exist_ok=True)
            file_name = f"{safe_filename(row['topic'])}-{safe_filename(resource_label(row['resource_type']))}.html"
            path = str(output_path / file_name)
            Path(path).write_text(file_text, encoding="utf-8")
            await state().db.save_resource(row, path)
            await state().db.set_job_done(job_id, path)
            caption = (
                "✅ <b>RESOURCE READY</b>\n"
                f"Exam: {html.escape(row['exam'])}\nSubject: {html.escape(row['subject'])}\n"
                f"Topic: {html.escape(row['topic'])}\nResource: {html.escape(resource_label(row['resource_type']))}\n"
                f"Language: {html.escape(row['language'])}\nFile: {html.escape(file_name)}"
            )
            with open(path, "rb") as document:
                await context.bot.send_document(row["chat_id"], document=document, filename=file_name, caption=caption, parse_mode="HTML")
            logger.info("Uploaded %s", file_name)
            if batch:
                await update_progress(batch, context, last=file_name)
        except Exception as exc:
            error = str(exc)[:2000]
            logger.error("Job %s failed: %s", job_id[:8], error)
            try:
                current_row = await state().db.get_job(job_id)
                attempts = int(current_row["attempts"]) if current_row else 1
                if attempts < max_external:
                    # AUTO-REPAIR: park back at PENDING so it is picked up again
                    await state().db.set_job_pending(job_id, f"Auto-retry {attempts}: {error}")
                    await state().queue.put(job_id)
                else:
                    # FINAL FAILED (bounded, never infinite)
                    await state().db.set_job_failed(job_id, error)
                    notify_row = current_row or row
                    if notify_row:
                        await context.bot.send_message(
                            notify_row["chat_id"],
                            f"❌ Job failed after {attempts} attempt(s)\n"
                            f"Topic: {notify_row['topic']}\nReason: {error}\nUse /retry to try failed jobs.",
                        )
                        batch = state().batches.get(notify_row["batch_id"])
                        if batch:
                            await update_progress(batch, context, force=True)
            except Exception:
                pass
        finally:
            state().queue.task_done()


async def _engine_final_report(batch: BatchState, context: ContextTypes.DEFAULT_TYPE, counts: dict[str, int]) -> None:
    """AUTO BUILD ALL finishing report: writes per-exam manifests, aggregates
    validated/required/repair/failed counts and only then claims completion."""
    try:
        exam_rows = await state().db.fetchall(
            "SELECT DISTINCT exam FROM jobs WHERE batch_id=? AND status IN ('COMPLETED','FAILED','CANCELLED')",
            (batch.batch_id,),
        )
        exam_names = [r["exam"] for r in exam_rows]
        manifests: list[dict[str, Any]] = []
        for exam in exam_names:
            try:
                manifests.append(write_exam_manifest(exam))
            except Exception:
                logger.exception("Manifest write failed for %s", exam)
        generated = sum(int(m.get("resources_generated", 0)) for m in manifests)
        validated = sum(int(m.get("resources_validated", 0)) for m in manifests)
        failed_resources = sum(int(m.get("resources_failed", 0)) for m in manifests)
        missing = sum(len(m.get("missing_resources", [])) for m in manifests)
        broken = sum(len(m.get("broken_links", [])) for m in manifests)
        duplicates = sum(len(m.get("duplicates", [])) for m in manifests)
        complete_exams = sum(1 for m in manifests if m.get("status") == "COMPLETE")
        histogram = await state().db.completed_attempt_counts(batch.batch_id)
        repaired = sum(count for attempts, count in histogram.items() if attempts > 1)
        failed_jobs = int(counts.get("FAILED", 0))

        single_exam = len(exam_names) == 1
        title = (
            f"🎉 <b>AUTO BUILD COMPLETE — {html.escape(exam_names[0])}</b>"
            if single_exam else "🎉 <b>AUTO BUILD ALL COMPLETE</b>"
        )
        lines = [
            title,
            f"Exams built: <b>{complete_exams}/{len(exam_names)}</b> fully complete · Failed jobs: {failed_jobs}",
            f"Resources generated: {generated} · validated: {validated} · repaired: {repaired} · failed: {failed_resources}",
            f"Missing: {missing} · broken links: {broken} · duplicates: {duplicates}",
        ]
        all_good = (
            complete_exams == len(exam_names)
            and failed_jobs == 0 and missing == 0 and broken == 0 and duplicates == 0 and failed_resources == 0
        )
        if all_good:
            lines.append("\n🏆 <b>ALL EXAMS 101% PREPARATION READY</b>")
            await state().db.finish_build(batch.batch_id, "COMPLETE")
        else:
            for manifest in manifests:
                if manifest.get("status") != "COMPLETE":
                    lines.append(f"⚠️ {html.escape(manifest.get('exam', ''))} — {manifest.get('status')}")
            lines.append("\n⚠️ <b>BUILD FINISHED WITH REVIEW REQUIRED</b>")
            lines.append("REBUILD FAILED / re-run AUTO BUILD ALL, then AUDIT ALL until every exam reports COMPLETE.")
            await state().db.finish_build(batch.batch_id, "REVIEW_REQUIRED")
        await context.bot.send_message(batch.chat_id, "\n".join(lines), parse_mode="HTML")
    except Exception:
        logger.exception("Engine final report failed")


async def finish_monitor(context: ContextTypes.DEFAULT_TYPE) -> None:
    for batch in list(state().batches.values()):
        counts = await state().db.job_counts(batch.batch_id)
        total = sum(counts.values())
        finished = counts.get("COMPLETED", 0) + counts.get("FAILED", 0) + counts.get("CANCELLED", 0)
        if total and finished >= total and not getattr(batch, "reported", False):
            setattr(batch, "reported", True)
            await update_progress(batch, context, force=True, last="Batch finished")
            if getattr(batch, "dashboard", False):
                await _engine_final_report(batch, context, counts)
            else:
                await context.bot.send_message(
                    batch.chat_id,
                    "🎉 <b>GENERATION COMPLETED</b>\n\n"
                    f"✅ Generated: {counts.get('COMPLETED', 0)}\n❌ Failed: {counts.get('FAILED', 0)}\n"
                    "📤 Completed files were uploaded individually.\n"
                    + ("Use /retry for failed jobs." if counts.get("FAILED", 0) else ""),
                    parse_mode="HTML",
                )
            # Refresh this batch's exam hub(s) + the root academy hub so the
            # OUTPUT folder always reads like a browsable website.
            exam_names: list[str] = []
            try:
                done_rows = await state().db.fetchall(
                    "SELECT DISTINCT exam FROM jobs WHERE batch_id=? AND status='COMPLETED'",
                    (batch.batch_id,),
                )
                exam_names = [r["exam"] for r in done_rows]
                if exam_names:
                    summary = rebuild_library(exam_names)
                    if summary["files"]:
                        await context.bot.send_message(
                            batch.chat_id,
                            f"🏠 Academy hubs refreshed for {len(exam_names)} exam(s).\n"
                            f"Library: {summary['files']} files across {summary['exams']} exams.\n"
                            "Open <code>OUTPUT/index.html</code> to browse like a website.",
                            parse_mode="HTML",
                        )
            except Exception:
                logger.exception("Hub refresh after batch failed")
            # AUTO-ZIP: the owner's daily flow builds ONE exam end-to-end, so when
            # a single-exam batch finishes cleanly, hand over the ready ZIP of it
            # right away — no separate CREATE ZIP tap needed.
            try:
                if getattr(batch, "dashboard", False) and len(exam_names) == 1:
                    zip_path = make_exam_zip(exam_names[0])
                    if zip_path:
                        await context.bot.send_message(
                            batch.chat_id,
                            "📦 <b>AUTO ZIP READY</b> — full exam pack below.",
                            parse_mode="HTML",
                        )
                        await send_zip_document(batch.chat_id, context, zip_path)
            except Exception:
                logger.exception("Auto ZIP after batch failed")


# ============================================================================ #
# JOB COMMANDS AND FILE HANDLING
# ============================================================================ #


async def status_command_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await state().db.recent_jobs(chat_id, 1)
    if not rows:
        await context.bot.send_message(chat_id, "No jobs found.")
        return
    row = rows[0]
    counts = await state().db.job_counts(row["batch_id"])
    await context.bot.send_message(
        chat_id,
        f"📊 Batch {row['batch_id'][:8]}\n"
        f"Exam: {row['exam']}\nLanguage: {row['language']}\n"
        f"Completed: {counts.get('COMPLETED', 0)}\nRunning: {counts.get('RUNNING', 0)}\n"
        f"Pending: {counts.get('PENDING', 0)}\nFailed: {counts.get('FAILED', 0)}",
        reply_markup=main_menu_keyboard(),
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await require_access(update):
        await status_command_for_chat(update.effective_chat.id, context)


async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    rows = await state().db.recent_jobs(update.effective_chat.id, 15)
    if not rows:
        await update.effective_message.reply_text("No jobs found.")
        return
    lines = ["📊 Recent jobs"]
    for row in rows:
        lines.append(f"{row['status']}: {row['topic']} — {resource_label(row['resource_type'])}")
    await update.effective_message.reply_text("\n".join(lines))


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the selected exam's explainable resource plan without generating."""
    if not await require_access(update):
        return
    current = state().contexts.get(update.effective_chat.id, {})
    exam = current.get("exam") or (context.args[0] if context.args else None)
    if exam not in EXAM_CONFIG:
        await update.effective_message.reply_text("Use /start first, or pass an exact exam name: /plan Gujarat Police Constable")
        return
    summary = plan_summary(exam, current.get("language"))
    registry = summary["registry"]
    await update.effective_message.reply_text(
        f"PLAN: {exam}\nLanguage: {summary['language']}\nSubjects: {summary['subjects_total']}\n"
        f"Syllabus units: {summary['units_total']}\nRequired HTML resources: {summary['resources_required']}\n"
        f"By scope: {summary['jobs_by_scope']}\nSyllabus status: {registry['syllabus_status']}\n"
        "Pending count is calculated from this plan; it is not itself proof of syllabus coverage."
    )


async def audit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/audit and /validate — offline validation + manifest sweep over every exam."""
    if await require_access(update):
        await audit_report_for_chat(update.effective_chat.id, context)


async def resume_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await state().db.pending_jobs(chat_id)
    if not rows:
        await context.bot.send_message(chat_id, "No pending jobs to resume.")
        return
    batch_ids = {row["batch_id"] for row in rows}
    for batch_id in batch_ids:
        if batch_id not in state().batches:
            state().batches[batch_id] = BatchState(batch_id=batch_id, chat_id=chat_id)
    for row in rows:
        await state().queue.put(row["job_id"])
    await context.bot.send_message(chat_id, f"🔄 Resumed {len(rows)} pending job(s).")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await require_access(update):
        await resume_for_chat(update.effective_chat.id, context)


async def retry_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await state().db.failed_jobs(chat_id)
    if not rows:
        await context.bot.send_message(chat_id, "No failed jobs to retry.")
        return
    for row in rows:
        await state().db.set_job_pending(row["job_id"], "Retry requested")
        await state().queue.put(row["job_id"])
    await context.bot.send_message(chat_id, f"🔁 Retrying {len(rows)} failed job(s).")


async def retry_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await require_access(update):
        await retry_for_chat(update.effective_chat.id, context)


async def stop_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stop must make ALL pending work for this chat actually stop — not
    just the batch object currently in memory. So this (1) flags every
    in-memory batch for this chat so workers reject them mid-loop, AND
    (2) cancels every PENDING/FAILED job for this chat straight in the
    DATABASE, so nothing left in the asyncio queue can start, and nothing
    can silently come back via /resume or a bot restart."""
    for batch in state().batches.values():
        if batch.chat_id == chat_id:
            batch.stopped.set()
    cancelled = await state().db.cancel_pending_for_chat(chat_id)
    await context.bot.send_message(
        chat_id,
        "🛑 Stop requested.\nJobs already running will finish safely (can't be interrupted mid-generation).\n"
        f"{cancelled} pending/failed job(s) were cancelled and will NOT run — including on /resume or a bot restart.",
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await require_access(update):
        await stop_for_chat(update.effective_chat.id, context)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reset — clear the ENTIRE build state for this chat, across every exam.
    Stops in-memory batches, cancels every running/pending/retrying/failed job in
    the database, and closes their engine builds. Old build screens and queued
    exams stop reappearing, and nothing silently resumes after a restart."""
    if not await require_access(update):
        return
    chat_id = update.effective_chat.id
    for batch_id in [b for b, batch in state().batches.items() if batch.chat_id == chat_id]:
        batch = state().batches.get(batch_id)
        if batch:
            batch.stopped.set()
        state().batches.pop(batch_id, None)
    cancelled = await state().db.cancel_all_for_chat(chat_id)
    cancelled_builds = await state().db.cancel_builds_for_chat(chat_id)
    await update.effective_message.reply_text(
        "🔄 <b>RESET COMPLETE</b>\n\n"
        f"Cleared <b>{cancelled}</b> job(s) and <b>{cancelled_builds}</b> build(s) "
        "across every exam. Nothing is queued anymore and nothing will auto-resume.\n\n"
        "⚠️ Files already mid-generation finish safely and upload once; no new file will start.\n"
        "Start fresh: /start → choose your exam → AUTO BUILD.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def cancel_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Standalone command for the 'bot restarted, discard old pending jobs'
    flow — same cancellation as /stop but without implying anything is
    currently running."""
    if await require_access(update):
        chat_id = update.effective_chat.id
        cancelled = await state().db.cancel_pending_for_chat(chat_id)
        await context.bot.send_message(
            chat_id,
            f"🗑️ {cancelled} pending/failed job(s) discarded." if cancelled else "No pending/failed jobs to discard.",
        )


def resource_zip_name(exam: str, count: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brand = ACADEMY_NAME.replace(" ", "")
    return f"{brand}-{safe_filename(exam)}-{count}-files-{stamp}.zip"


def make_exam_zip(exam: str) -> Optional[Path]:
    """Pack EVERY HTML file generated for this exam (including its hub) into
    one ZIP, addressed as <exam>/<subject>/<resource>/<file>."""
    files = exam_html_files(exam)
    if not files:
        return None
    zip_path = Path(OUTPUT_DIR) / resource_zip_name(exam, len(files))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, file_path.relative_to(OUTPUT_DIR).as_posix())
    return zip_path


def make_combined_zip() -> Optional[Path]:
    """Single ZIP of every exam library, preserving the per-exam folders."""
    exams = built_exams()
    if not exams:
        return None
    total = sum(len(exam_html_files(exam)) for exam in exams)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brand = ACADEMY_NAME.replace(" ", "")
    zip_path = Path(OUTPUT_DIR) / f"{brand}-All-Exams-{total}-files-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for exam in exams:
            for file_path in exam_html_files(exam):
                archive.write(file_path, file_path.relative_to(OUTPUT_DIR).as_posix())
    return zip_path


def rebuild_library(exams: Optional[list[str]] = None) -> dict[str, Any]:
    """(Re)generate the exam hub pages + the root academy hub over the current
    OUTPUT library. Returns a small summary for messaging."""
    targets = [e for e in (exams or built_exams()) if e in EXAM_CONFIG]
    refreshed = 0
    for exam in targets:
        if not exam_html_files(exam):
            continue
        try:
            build_exam_hub(exam)
            refreshed += 1
        except Exception as exc:  # a hub must never break the bot
            logger.warning("Hub build failed for %s: %s", exam, exc)
    root = build_academy_hub()
    return {"hubs": refreshed, "files": int(root.get("files", 0)), "exams": int(root.get("exams", 0))}


async def rebuild_hubs_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    summary = rebuild_library()
    if summary["exams"] == 0:
        await context.bot.send_message(chat_id, "No generated files found yet — build something first (AUTO BUILD ALL), then rebuild hubs.")
        return
    await context.bot.send_message(
        chat_id,
        "🏠 <b>ACADEMY HUBS REBUILT</b>\n\n"
        f"Exam hubs refreshed: {summary['hubs']}\n"
        f"Library now has {summary['files']} files across {summary['exams']} exams.\n\n"
        "Open <code>OUTPUT/index.html</code> to browse the whole academy like a website — "
        "each exam folder has its own searchable <code>index.html</code> hub.",
        parse_mode="HTML",
    )


async def send_zip_document(chat_id: int, context: ContextTypes.DEFAULT_TYPE, zip_path: Path) -> None:
    with open(zip_path, "rb") as document:
        await context.bot.send_document(
            chat_id,
            document=document,
            filename=zip_path.name,
            caption=f"📦 {zip_path.name}\n{ACADEMY_NAME} — download & open <code>index.html</code> inside to browse.",
            parse_mode="HTML",
        )


async def zip_exam_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE, exam: str) -> None:
    zip_path = make_exam_zip(exam)
    if not zip_path:
        await context.bot.send_message(chat_id, f"No generated files for {exam} yet.")
        return
    await send_zip_document(chat_id, context, zip_path)


async def zip_all_exams_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    exams = built_exams()
    if not exams:
        await context.bot.send_message(chat_id, "No generated files are available for a ZIP yet.")
        return
    sent = 0
    for exam in exams:
        try:
            zip_path = make_exam_zip(exam)
            if zip_path:
                await send_zip_document(chat_id, context, zip_path)
                sent += 1
        except Exception as exc:
            logger.warning("ZIP failed for %s: %s", exam, exc)
    if sent:
        await context.bot.send_message(chat_id, f"✅ Sent {sent} exam ZIP(s) — one per exam, each containing every HTML file made for it so far.")


async def zip_everything_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    zip_path = make_combined_zip()
    if not zip_path:
        await context.bot.send_message(chat_id, "No generated files are available for a ZIP yet.")
        return
    await send_zip_document(chat_id, context, zip_path)


async def create_zip_for_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CREATE ZIP now opens a chooser. Every option packs files straight off
    disk, so a ZIP always contains ALL HTML files ever generated for an exam —
    not only the jobs still recorded in this chat's database."""
    built = built_exams()
    if not built:
        await context.bot.send_message(chat_id, "No generated files are available for a ZIP yet.\nGenerate resources first (AUTO BUILD ALL), then come back here.")
        return
    await context.bot.send_message(
        chat_id,
        "📦 <b>ZIP YOUR LIBRARY</b>\n\n"
        "Every option packs <b>all HTML files the AI has generated so far</b> — each exam gets its own ZIP with its hub page inside.",
        parse_mode="HTML",
        reply_markup=zip_options_keyboard(chat_id),
    )


async def zip_option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not await require_access(update):
        return
    await query.answer()
    chat_id = query.message.chat_id
    choice = (query.data or "").split(":", 1)[1]
    if choice == "exam":
        exam = state().contexts.get(chat_id, {}).get("exam")
        if not exam or exam not in EXAM_CONFIG:
            await context.bot.send_message(chat_id, "No exam selected. Use /start to pick an exam, or choose a different ZIP option.")
            return
        await zip_exam_for_chat(chat_id, context, exam)
    elif choice == "all":
        await zip_all_exams_for_chat(chat_id, context)
    elif choice == "single":
        await zip_everything_for_chat(chat_id, context)
    else:
        await create_zip_for_chat(chat_id, context)


async def zip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await require_access(update):
        await create_zip_for_chat(update.effective_chat.id, context)


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    message = update.effective_message
    if not message or not message.document:
        return
    chat_id = update.effective_chat.id
    suffix = Path(message.document.file_name or "source.txt").suffix.lower()
    if suffix not in {".pdf", ".txt", ".md", ".csv"}:
        await message.reply_text("Please send a PDF, TXT, MD, or CSV source file.")
        return
    file = await context.bot.get_file(message.document.file_id)
    destination = Path(SOURCE_DIR) / f"{chat_id}-{uuid.uuid4().hex}{suffix}"
    await file.download_to_drive(str(destination))
    state().source_paths[chat_id] = str(destination)
    state().contexts.setdefault(chat_id, {})["source_path"] = str(destination)
    await message.reply_text(
        f"✅ Source saved: {message.document.file_name}\nChoose what to build from this source.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, callback_data=f"source:{kind}")] for kind, label in [("Notes", "Notes"), ("PYQ", "PYQ"), ("Practice", "Practice"), ("Topic-Test", "Test")]]
        ),
    )


async def source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not await require_access(update):
        return
    await query.answer()
    chat_id = query.message.chat_id
    kind = (query.data or "").split(":", 1)[1]
    current = state().contexts.get(chat_id, {})
    exam = current.get("exam")
    language = current.get("language")
    if not exam or not language:
        await query.edit_message_text("Use /start first, then upload the source again.")
        return
    topic = Path(state().source_paths.get(chat_id, "Source")).stem
    await query.edit_message_text(f"Source selected for {kind}. Starting generation…")
    await start_batch(chat_id, context, exam, language, [(current.get("subject", EXAM_CONFIG[exam]["subjects"][0]), topic)], [kind])


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    chat_id = update.effective_chat.id
    current = state().contexts.setdefault(chat_id, {})
    raw = text_from_message(update.effective_message)
    if current.get("awaiting_prompt"):
        await handle_prompt_text(chat_id, raw, context)
    elif current.get("awaiting_source"):
        await update.effective_message.reply_text("Please send the source as a PDF or TXT document.")


# ============================================================================ #
# OWNER ACCESS COMMANDS
# ============================================================================ #


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("Usage: /adduser USER_ID")
        return
    user_id = int(context.args[0])
    await state().db.add_user(user_id, update.effective_user.id)
    await update.effective_message.reply_text(f"✅ User authorized: {user_id}")


async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("Usage: /removeuser USER_ID")
        return
    user_id = int(context.args[0])
    await state().db.remove_user(user_id)
    await update.effective_message.reply_text(f"✅ User removed: {user_id}")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    rows = await state().db.fetchall("SELECT user_id, added_by, created_at FROM users ORDER BY created_at")
    await update.effective_message.reply_text("Authorized users:\n" + ("\n".join(str(row["user_id"]) for row in rows) if rows else "None"))


async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    chat = update.effective_chat
    if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        await update.effective_message.reply_text("Use /addgrup inside the group you want to authorize.")
        return
    await state().db.add_group(chat.id, chat.title or "Untitled group", update.effective_user.id)
    await update.effective_message.reply_text(f"✅ GROUP AUTHORIZED\nGroup: {chat.title}\nID: {chat.id}")


async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    chat_id: Optional[int] = update.effective_chat.id if update.effective_chat.type in {ChatType.GROUP, ChatType.SUPERGROUP} else None
    if context.args and context.args[0].lstrip("-").isdigit():
        chat_id = int(context.args[0])
    if chat_id is None:
        await update.effective_message.reply_text("Usage inside a group: /removegrup, or /removegrup CHAT_ID")
        return
    await state().db.remove_group(chat_id)
    await update.effective_message.reply_text(f"✅ Group removed: {chat_id}")


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    rows = await state().db.fetchall("SELECT chat_id, title, owner_id, created_at FROM groups ORDER BY created_at")
    if not rows:
        await update.effective_message.reply_text("Authorized groups: None")
        return
    await update.effective_message.reply_text("Authorized groups:\n" + "\n".join(f"{row['title']} ({row['chat_id']})" for row in rows))


# ============================================================================ #
# APPLICATION LIFECYCLE
# ============================================================================ #


async def post_init(application: Application) -> None:
    global STATE
    db = Database(DATABASE_PATH)
    await db.initialize()
    ai = AIClient()
    await ai.start()
    STATE = FactoryState(db=db, ai=ai)
    for worker_id in range(MAX_WORKERS):
        STATE.workers.append(asyncio.create_task(worker(worker_id, application)))
    application.job_queue.run_repeating(finish_monitor, interval=5, first=5)
    # IMPORTANT: do NOT auto-enqueue old pending jobs on startup. A restart
    # (bot turned off/on days later) must never silently start generating
    # files the user never asked for in this session. Just tell each chat
    # how many jobs are waiting; they explicitly choose /resume or /cancelpending.
    pending = await db.pending_jobs()
    by_chat: dict[int, int] = {}
    for row in pending:
        by_chat[row["chat_id"]] = by_chat.get(row["chat_id"], 0) + 1
    for chat_id, count in by_chat.items():
        try:
            await application.bot.send_message(
                chat_id,
                f"ℹ️ Bot restarted. {count} job(s) from before are still PENDING and were NOT started "
                "automatically.\nSend /resume to continue them, or /cancelpending to discard them.",
            )
        except Exception:
            logger.warning("Could not notify chat %s about pending jobs", chat_id)
    logger.info("Sonic Resource Factory started with %s pending job(s) awaiting /resume", len(pending))


async def post_shutdown(application: Application) -> None:
    if STATE:
        for worker_task in STATE.workers:
            worker_task.cancel()
        await asyncio.gather(*STATE.workers, return_exceptions=True)
        await STATE.ai.close()


def build_application() -> Application:
    if is_placeholder(BOT_TOKEN):
        raise RuntimeError("BOT_TOKEN is not configured. Edit the configuration at the top of bot.py.")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prompt", prompt_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("jobs", jobs_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("retry", retry_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("cancelpending", cancel_pending_command))
    app.add_handler(CommandHandler("cancel", stop_command))
    app.add_handler(CommandHandler("zip", zip_command))
    app.add_handler(CommandHandler("adduser", add_user_command))
    app.add_handler(CommandHandler("removeuser", remove_user_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("addgrup", add_group_command))
    app.add_handler(CommandHandler("removegrup", remove_group_command))
    app.add_handler(CommandHandler("groups", groups_command))
    app.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^(exam|lang|menu):"))
    app.add_handler(CallbackQueryHandler(resource_callback, pattern=r"^resource:"))
    app.add_handler(CallbackQueryHandler(source_callback, pattern=r"^source:"))
    app.add_handler(CallbackQueryHandler(zip_option_callback, pattern=r"^zipopt:"))
    app.add_handler(CallbackQueryHandler(eng_callback, pattern=r"^eng:"))
    app.add_handler(CallbackQueryHandler(pick_exam_callback, pattern=r"^pickexam:"))
    app.add_handler(CallbackQueryHandler(autolang_callback, pattern=r"^autolang:"))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("audit", audit_command))
    app.add_handler(CommandHandler("validate", audit_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return app


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = build_application()
    logger.info("Starting Telegram polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()
