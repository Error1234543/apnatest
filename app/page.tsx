'use client'

import { useState } from 'react'
import { ArrowRight, BookOpen, Camera, Check, ChevronDown, GraduationCap, Menu, Moon, Search, Send, Sparkles, Sun, Target, X } from 'lucide-react'

const telegramChannel = 'https://t.me/+NGUSfa7ns8c4OTll'
const instagram = 'https://www.instagram.com/xdsonicai?obrf=ZmVweHAzaGVoMXpr'
const contact = 'https://t.me/Prepgridoffical'

const exams = [
  { title: 'NEET UG', subtitle: 'Medical entrance preparation', icon: '✦', color: '#ef4444', tags: ['Biology', 'Physics', 'Chemistry'] },
  { title: 'JEE', subtitle: 'Engineering entrance preparation', icon: '∑', color: '#6366f1', tags: ['PCM', 'PYQs', 'Mocks'] },
  { title: 'GUJCET', subtitle: 'Gujarat common entrance test', icon: '⌁', color: '#0ea5e9', tags: ['Science', 'Gujarati', 'Tests'] },
  { title: 'Gujarat Board', subtitle: 'Class 10 & 12 resources', icon: '▣', color: '#f59e0b', tags: ['GSEB', 'Notes', 'Revision'] },
  { title: 'GPSC', subtitle: 'Gujarat public service commission', icon: '◆', color: '#10b981', tags: ['GK', 'Current Affairs', 'Mocks'] },
  { title: 'GSSSB', subtitle: 'Gujarat subordinate services', icon: '◈', color: '#ec4899', tags: ['Gujarati', 'Reasoning', 'Practice'] },
  { title: 'TET / CTET', subtitle: 'Teacher eligibility preparation', icon: '◇', color: '#8b5cf6', tags: ['Pedagogy', 'Language', 'Mock Tests'] },
  { title: 'Police & Defence', subtitle: 'Constable and competitive exams', icon: '★', color: '#f97316', tags: ['Fitness', 'GK', 'Practice'] },
]

const plans = [
  ['1 Month', '₹199'], ['3 Months', '₹499'], ['4 Months', '₹649'], ['6 Months', '₹899'], ['NEET 2027 Full Course', '₹999'],
]

const benefits = ['Daily Study Guidance', 'Chapter-wise MCQs', 'PYQs', 'Regular Tests & Mocks', 'Revision Planning', 'Doubt Support', 'Progress Tracking', 'Gujarati + English Support', 'Complete Guidance till NEET 2027']

const faqs = [
  ['What is PrepGrid?', 'PrepGrid is a focused exam-preparation hub for students preparing for NEET, JEE, Gujarat competitive exams, board exams and teacher eligibility tests.'],
  ['How do I join NEET 2027 mentorship?', 'Tap any Join Mentorship button and send JOIN on Telegram. The team will share the next steps and plan details.'],
  ['Is support available in Gujarati?', 'Yes. PrepGrid supports Gujarati and English so learners can study comfortably in the language they understand best.'],
]

export default function Page() {
  const [dark, setDark] = useState(true)
  const [menu, setMenu] = useState(false)
  const [query, setQuery] = useState('')
  const [openFaq, setOpenFaq] = useState<number | null>(null)
  const filtered = exams.filter((exam) => `${exam.title} ${exam.subtitle} ${exam.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className={dark ? 'site dark' : 'site'}>
      <div className="aurora aurora-one" /><div className="aurora aurora-two" /><div className="grid-bg" />
      <header className="nav"><div className="nav-inner">
        <a href="#top" className="brand"><span className="brand-mark"><GraduationCap size={20} /></span><span><strong>PrepGrid</strong><small>INDIA&apos;S EXAM PREP HUB</small></span></a>
        <nav className="desktop-nav"><a href="#exams">Exam Spaces</a><a href="#why">Why Us</a><a href="#mentorship">Mentorship</a><a href="#faq">FAQ</a></nav>
        <div className="nav-actions"><a className="button button-primary nav-join" href={telegramChannel} target="_blank" rel="noreferrer"><Send size={16} /> Join Telegram</a><button className="icon-button" onClick={() => setDark(!dark)} aria-label="Toggle theme">{dark ? <Sun size={18} /> : <Moon size={18} />}</button><button className="icon-button mobile-menu" onClick={() => setMenu(!menu)} aria-label="Toggle menu">{menu ? <X size={20} /> : <Menu size={20} />}</button></div>
      </div>{menu && <nav className="mobile-nav"><a href="#exams" onClick={() => setMenu(false)}>Exam Spaces</a><a href="#why" onClick={() => setMenu(false)}>Why Us</a><a href="#mentorship" onClick={() => setMenu(false)}>Mentorship</a><a href="#faq" onClick={() => setMenu(false)}>FAQ</a></nav>}</header>

      <main id="top">
        <section className="hero container"><div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> Structured preparation. Better results.</div><h1>Build your edge.<br /><span>Clear your exam.</span></h1><p>Premium study spaces, chapter-wise practice, PYQs and mentorship for India&apos;s most important entrance and competitive exams.</p><div className="hero-actions"><a className="button button-primary" href="#exams">Explore exam spaces <ArrowRight size={17} /></a><a className="button button-ghost" href="#mentorship">View mentorship</a></div><div className="hero-proof"><span className="avatar-stack"><i /><i /><i /></span><span><strong>Focused guidance</strong><small>Gujarati + English support</small></span></div></div><div className="hero-visual"><div className="orbit orbit-a" /><div className="orbit orbit-b" /><div className="hero-card"><div className="hero-card-top"><span className="status-dot" /> LIVE STUDY SYSTEM <span>2027</span></div><div className="hero-card-icon"><BookOpen size={30} /></div><h3>Your next chapter<br /><span>starts here.</span></h3><div className="progress"><div><span>Weekly focus</span><b>78%</b></div><div className="progress-track"><i /></div></div><div className="mini-stats"><span><b>12</b><small>Tests</small></span><span><b>48</b><small>Chapters</small></span><span><b>24/7</b><small>Access</small></span></div></div></div></section>

        <section className="marquee"><div>MCQs <b>•</b> PYQs <b>•</b> MOCK TESTS <b>•</b> REVISION PLANS <b>•</b> DOUBT SUPPORT <b>•</b> TRACK YOUR PROGRESS <b>•</b></div></section>

        <section id="exams" className="section container"><div className="section-heading"><div><span className="eyebrow">01 / Study spaces</span><h2>Choose your <span>arena.</span></h2></div><div className="search"><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search an exam..." aria-label="Search exams" /></div></div><div className="folder-grid">{filtered.map((exam) => <article className="folder-wrap" key={exam.title} style={{ '--accent': exam.color } as React.CSSProperties}><div className="folder"><div className="folder-tab" /><div className="folder-back" /><div className="folder-front"><div className="folder-top"><span className="folder-icon">{exam.icon}</span><span className="folder-arrow"><ArrowRight size={16} /></span></div><div><h3>{exam.title}</h3><p>{exam.subtitle}</p></div><div className="tag-row">{exam.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><a className="folder-link" href={contact} target="_blank" rel="noreferrer">Open space <ArrowRight size={14} /></a></div></div></article>)}</div>{filtered.length === 0 && <div className="empty">No exam space found. Try another search.</div>}</section>

        <section id="why" className="section feature-section"><div className="container"><div className="section-heading"><div><span className="eyebrow">02 / The PrepGrid method</span><h2>Study with <span>clarity.</span></h2></div><p className="heading-note">Less noise. More intentional practice. A clear path from today&apos;s study session to your exam day.</p></div><div className="feature-grid"><div className="feature-card featured"><Target size={25} /><span className="feature-number">01</span><h3>Know what to study</h3><p>Follow structured, chapter-wise resources that keep your preparation focused and measurable.</p></div><div className="feature-card"><Check size={25} /><span className="feature-number">02</span><h3>Practice the right way</h3><p>Build confidence with MCQs, PYQs, regular tests and realistic mock exams.</p></div><div className="feature-card"><BookOpen size={25} /><span className="feature-number">03</span><h3>Revise with a plan</h3><p>Turn revision into a repeatable routine with progress tracking and smart planning.</p></div></div></div></section>

        <section id="mentorship" className="section container"><div className="mentorship"><div className="mentorship-copy"><span className="eyebrow">03 / NEET 2027 mentorship</span><h2>One plan.<br /><span>Every milestone.</span></h2><p>Proper guidance and preparation support from now until NEET 2027. Join once and keep moving with a clear plan.</p><a className="button button-light" href={contact} target="_blank" rel="noreferrer">Reply &quot;JOIN&quot; on Telegram <ArrowRight size={17} /></a></div><div className="plans"><div className="best-value">BEST VALUE</div>{plans.map(([name, price]) => <div className={name.includes('Full') ? 'plan active' : 'plan'} key={name}><span>{name}</span><strong>{price}</strong>{name.includes('Full') && <small>Continue till NEET 2027</small>}</div>)}<div className="mentorship-foot">Secure guidance for every stage of your preparation.</div></div></div><div className="benefits"><div><span className="eyebrow">What&apos;s included</span><h3>Everything you need to stay consistent.</h3></div><div className="benefit-list">{benefits.map((item) => <span key={item}><Check size={15} /> {item}</span>)}</div></div></section>

        <section id="faq" className="section container faq-section"><div className="section-heading"><div><span className="eyebrow">04 / Questions</span><h2>Clear answers.</h2></div><p className="heading-note">Still unsure? Send us a message on Telegram and we&apos;ll help you choose the right path.</p></div><div className="faq-list">{faqs.map(([q, a], i) => <div className={openFaq === i ? 'faq open' : 'faq'} key={q}><button onClick={() => setOpenFaq(openFaq === i ? null : i)} aria-expanded={openFaq === i}><span>{q}</span><ChevronDown size={18} /></button>{openFaq === i && <p>{a}</p>}</div>)}</div></section>
      </main>

      <footer id="connect" className="footer"><div className="container footer-grid"><div><a href="#top" className="brand"><span className="brand-mark"><GraduationCap size={20} /></span><span><strong>PrepGrid</strong><small>PREPARE WITH PURPOSE</small></span></a><p>Focused exam preparation for ambitious learners.</p></div><div><h4>Connect</h4><a href={telegramChannel} target="_blank" rel="noreferrer"><Send size={15} /> Join Telegram channel</a><a href={contact} target="_blank" rel="noreferrer"><Send size={15} /> @{`Prepgridoffical`}</a><a href={instagram} target="_blank" rel="noreferrer"><Camera size={15} /> Instagram</a></div><div><h4>Explore</h4><a href="#exams">Exam Spaces</a><a href="#mentorship">NEET 2027 Mentorship</a><a href="#faq">FAQs</a></div></div><div className="container footer-bottom"><span>© 2027 PrepGrid Official Academy</span><span>Built for consistent preparation.</span></div></footer>
    </div>
  )
}
