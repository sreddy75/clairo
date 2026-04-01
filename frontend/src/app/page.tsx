'use client';

import { motion, useScroll, useTransform } from 'framer-motion';
import {
  ArrowRight,
  BarChart3,
  Bot,
  Calculator,
  ChevronDown,
  Clock,
  FileText,
  Layers,
  LineChart,
  MessageSquare,
  Scale,
  Search,
  Shield,
  Users,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useRef } from 'react';

import { ClairoLogo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme';

// ============================================================================
// HEADER
// ============================================================================

function Header() {
  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6 }}
      className="fixed top-0 left-0 right-0 z-50 bg-card/90 backdrop-blur-md border-b border-border/60"
    >
      <nav className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center">
            <ClairoLogo size="lg" variant="light" className="dark:hidden" />
            <ClairoLogo size="lg" variant="dark" className="hidden dark:flex" />
          </Link>

          <div className="hidden md:flex items-center gap-10">
            <a href="#platform" className="text-sm text-muted-foreground hover:text-foreground transition-colors font-medium">
              Platform
            </a>
            <a href="#launching-with" className="text-sm text-muted-foreground hover:text-foreground transition-colors font-medium">
              Launching With
            </a>
            <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors font-medium">
              How It Works
            </a>
            <a href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors font-medium">
              Pricing
            </a>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/sign-in"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/sign-up"
              className="px-5 py-2.5 text-sm font-semibold text-background bg-foreground hover:bg-foreground/90 rounded-full transition-all shadow-sm hover:shadow-md"
            >
              Request Early Access
            </Link>
          </div>
        </div>
      </nav>
    </motion.header>
  );
}

// ============================================================================
// HERO
// ============================================================================

function HeroSection() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end start'],
  });
  const y = useTransform(scrollYProgress, [0, 1], [0, 200]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <section ref={ref} className="relative min-h-screen bg-background overflow-hidden pt-16">
      <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.05]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
      }} />

      <motion.div style={{ y, opacity }} className="relative z-10">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 pt-20 lg:pt-32">
          <div className="max-w-4xl">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-8"
            >
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                For Australian Accounting Practices
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.8 }}
              className="font-serif text-5xl sm:text-6xl lg:text-7xl xl:text-8xl font-light text-foreground leading-[0.95] tracking-tight mb-8"
            >
              The workhorse
              <br />
              <span className="font-normal italic text-muted-foreground">your practice deserves.</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="text-xl lg:text-2xl text-muted-foreground max-w-2xl leading-relaxed mb-10 font-light"
            >
              Clairo is an AI practice platform that does the heavy lifting across compliance, advisory, and client management
              — so you can focus on the work that matters.
              Built for Australian accountants. Powered by deep Xero integration and ATO-specific AI.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="flex flex-col sm:flex-row gap-4"
            >
              <Link
                href="/sign-up"
                className="group inline-flex items-center justify-center gap-3 px-8 py-4 bg-foreground hover:bg-foreground/90 text-background font-semibold rounded-full transition-all shadow-lg hover:shadow-xl"
              >
                Request Early Access
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <a
                href="#platform"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 text-foreground font-semibold border-2 border-border hover:border-foreground/30 rounded-full transition-all"
              >
                See the Platform
              </a>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
          >
            <span className="text-xs text-muted-foreground uppercase tracking-widest">Scroll</span>
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
            >
              <ChevronDown className="w-5 h-5 text-muted-foreground" />
            </motion.div>
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}

// ============================================================================
// PROBLEM
// ============================================================================

function ProblemSection() {
  return (
    <section className="py-24 lg:py-32 bg-muted/30">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-3xl"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-8">
            Your practice runs on a dozen tools that don&apos;t talk to each other.
          </h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-12">
            You&apos;re logging into Xero to check numbers, switching to a spreadsheet to run tax scenarios,
            chasing clients for documents over email, and hoping nothing falls through the cracks.
            Every practice runs this way. None of them should have to.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            { stat: '12+', label: 'hours/week checking client status across tools', icon: Clock },
            { stat: '50', label: 'Xero logins just to see what needs attention today', icon: Search },
            { stat: '30min', label: 'per client to manually pull and format tax data', icon: FileText },
            { stat: '0', label: 'visibility into what you missed last quarter', icon: BarChart3 },
          ].map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="bg-card rounded-xl p-6 border border-border"
            >
              <item.icon className="w-5 h-5 text-muted-foreground mb-3" />
              <p className="text-3xl font-light text-foreground mb-1">{item.stat}</p>
              <p className="text-sm text-muted-foreground">{item.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PLATFORM - What Clairo actually is
// ============================================================================

function PlatformSection() {
  return (
    <section id="platform" className="py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-3xl mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-6">
            One platform. Every workflow.
          </h2>
          <p className="text-lg text-muted-foreground leading-relaxed">
            Clairo is a practice intelligence platform that connects your Xero data to AI trained on Australian tax law.
            Each module tackles a different part of your workflow — BAS, tax planning, client management, and more as the platform grows.
            You&apos;re not buying a point solution. You&apos;re buying into a workhorse that gets more capable every quarter.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8">
          {/* Foundation layer */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-card rounded-xl p-8 border border-border"
          >
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center mb-5">
              <Layers className="w-5 h-5 text-blue-500" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-3">Deep Xero Integration</h3>
            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
              We sync everything — P&L, balance sheets, bank transactions, credit notes, journals, fixed assets, payments, purchase orders.
              Not just invoices. Everything.
            </p>
            <p className="text-xs text-muted-foreground/70">30+ entity types synced in real-time</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="bg-card rounded-xl p-8 border border-border"
          >
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center mb-5">
              <Scale className="w-5 h-5 text-emerald-500" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-3">ATO-Trained AI</h3>
            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
              Our knowledge base ingests ATO rulings, legislation, case law, and tax rates.
              When the AI advises on a scenario, it cites the relevant provision — not a hallucinated one.
            </p>
            <p className="text-xs text-muted-foreground/70">Hybrid search with cross-encoder reranking</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="bg-card rounded-xl p-8 border border-border"
          >
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center mb-5">
              <Bot className="w-5 h-5 text-amber-500" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-3">Specialist AI Agents</h3>
            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
              Multiple AI agents analyse each situation from different angles — compliance, quality, cash flow, strategy.
              When they converge, you get options with trade-offs, not just a single answer.
            </p>
            <p className="text-xs text-muted-foreground/70">Proactive insights surfaced daily</p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// LAUNCHING WITH — BAS + Tax Planning
// ============================================================================

function LaunchingWithSection() {
  return (
    <section id="launching-with" className="py-24 lg:py-32 bg-muted/30">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-3xl mb-16"
        >
          <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-4">First off the rank</p>
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-6">
            BAS workflow and AI tax planning — ready for EOFY.
          </h2>
          <p className="text-lg text-muted-foreground leading-relaxed">
            We&apos;re launching with the two workflows every practice runs during April–June.
            These are production-ready today, with more modules shipping quarterly.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* BAS Module */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-card rounded-xl border border-border overflow-hidden"
          >
            <div className="p-8 border-b border-border bg-gradient-to-br from-blue-500/5 to-transparent">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-blue-500" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">End-to-End BAS</h3>
                  <p className="text-xs text-muted-foreground">Compliance workflow</p>
                </div>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Pull financials from Xero, calculate BAS fields, resolve unmapped tax codes with AI suggestions,
                and track every change in a tamper-evident audit trail. Your clients classify their own uncertain transactions
                via a magic link — no chasing.
              </p>
            </div>
            <div className="p-6 space-y-3">
              {[
                'AI resolves unmapped tax codes (NONE, BASEXCLUDED) with confidence tiers',
                'Client portal — business owners classify transactions via magic link',
                'Full BAS field calculation with variance analysis',
                'Audit trail satisfies ATO 7-year retention requirements',
                'Data quality scoring flags issues before you start',
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3 text-sm text-muted-foreground">
                  <Zap className="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Tax Planning Module */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="bg-card rounded-xl border border-border overflow-hidden"
          >
            <div className="p-8 border-b border-border bg-gradient-to-br from-emerald-500/5 to-transparent">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <Calculator className="w-5 h-5 text-emerald-500" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">AI Tax Planning</h3>
                  <p className="text-xs text-muted-foreground">Advisory workflow</p>
                </div>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Pull a client&apos;s P&L and bank balances from Xero, see their estimated tax position in seconds,
                then describe a scenario in plain English and let the AI model strategies with real numbers, compliance notes,
                and risk ratings.
              </p>
            </div>
            <div className="p-6 space-y-3">
              {[
                'Xero P&L auto-pulled with bank balances and reconciliation status',
                'Accurate tax calculations — company, individual, trust, partnership',
                'AI scenario modelling: "what if we prepay $30K rent before June 30?"',
                'Each scenario shows tax saving, cash flow impact, and ATO risk rating',
                'Export client-ready PDF with practice branding and disclaimers',
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3 text-sm text-muted-foreground">
                  <Zap className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Coming next */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="mt-12 bg-card rounded-xl border border-border p-8"
        >
          <h3 className="text-base font-semibold text-foreground mb-4">Coming next on the platform</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Shield, label: 'ATO Correspondence Tracking', desc: 'Parse, track, and never miss a deadline' },
              { icon: MessageSquare, label: 'Voice Feedback Portal', desc: 'Clients leave voice notes, AI transcribes and routes' },
              { icon: LineChart, label: 'Cash Flow Forecasting', desc: 'Forward projections from live Xero data' },
              { icon: Users, label: 'Multi-Entity Groups', desc: 'Family trusts, companies, consolidated views' },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3">
                <item.icon className="w-5 h-5 text-muted-foreground/50 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// HOW IT WORKS — Simple flow
// ============================================================================

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-6">
            How it works
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Connect once. Clairo does the rest.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-12">
          {[
            {
              step: '01',
              title: 'Connect Xero',
              desc: 'One OAuth click. We sync your entire client portfolio — financials, transactions, contacts, journals, assets. Everything.',
            },
            {
              step: '02',
              title: 'AI analyses everything',
              desc: 'Specialist agents scan every client for compliance gaps, data quality issues, tax planning opportunities, and cash flow risks. Proactively.',
            },
            {
              step: '03',
              title: 'You act on what matters',
              desc: 'Open your dashboard. See which clients need attention today. Run a BAS, model a tax scenario, or send a client a document request — all from one place.',
            },
          ].map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              className="text-center"
            >
              <p className="text-5xl font-light text-muted-foreground/30 mb-4">{item.step}</p>
              <h3 className="text-lg font-semibold text-foreground mb-3">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// VALUE — Fair value for both practice and clients
// ============================================================================

function ValueSection() {
  return (
    <section className="py-24 lg:py-32 bg-muted/30">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-3xl mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-6">
            Fair value for your practice and your clients.
          </h2>
          <p className="text-lg text-muted-foreground leading-relaxed">
            Clairo doesn&apos;t just save you time. It elevates the quality of service your clients receive
            — more accurate BAS, proactive tax advice, and a portal where they can participate in the process.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            {
              title: 'From data entry to advisory',
              desc: 'Stop typing numbers from Xero into spreadsheets. Start modelling tax strategies with AI that knows the ATO rules.',
              icon: TrendingUp,
            },
            {
              title: 'Clients in the loop',
              desc: 'Business owners classify their own transactions, upload documents, and leave voice feedback — all through a simple portal.',
              icon: Users,
            },
            {
              title: 'Nothing slips through',
              desc: 'AI agents scan your portfolio daily. Unmapped tax codes, quality issues, and approaching thresholds are surfaced before they become problems.',
              icon: Shield,
            },
            {
              title: 'Compliance you can trust',
              desc: 'Every AI suggestion requires your approval. Every change is audit-logged. The AI assists — you decide.',
              icon: Scale,
            },
            {
              title: 'Platform that grows with you',
              desc: 'BAS and tax planning are the first modules. New capabilities ship quarterly. Your subscription gets more valuable over time, not more expensive.',
              icon: Layers,
            },
            {
              title: 'Built for Australian practices',
              desc: 'GST, BAS, PAYG, FBT, Division 7A, Part IVA — the AI speaks your language because it was trained on your domain.',
              icon: Zap,
            },
          ].map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="bg-card rounded-xl p-6 border border-border"
            >
              <item.icon className="w-5 h-5 text-primary mb-3" />
              <h3 className="text-base font-semibold text-foreground mb-2">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PRICING — Outcome-based teaser
// ============================================================================

function PricingSection() {
  return (
    <section id="pricing" className="py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-3xl mx-auto text-center"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-6">
            Pricing that reflects results, not seats.
          </h2>
          <p className="text-lg text-muted-foreground leading-relaxed mb-12">
            We don&apos;t think you should pay more because you have more logins.
            You should pay based on the value you get — the clients you serve, the work Clairo handles for you.
            We&apos;re finalising our pricing model with early access partners now.
          </p>

          <div className="bg-card rounded-2xl border border-border p-10 text-left">
            <div className="grid sm:grid-cols-3 gap-8 mb-10">
              <div>
                <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-2">What you get</p>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Full platform access</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> BAS + Tax Planning modules</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Deep Xero integration</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> ATO knowledge base</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Client portal</li>
                </ul>
              </div>
              <div>
                <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-2">How we price</p>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Based on clients managed</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Not per seat or per login</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> New modules included</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> No lock-in contracts</li>
                  <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Free onboarding support</li>
                </ul>
              </div>
              <div>
                <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-2">Early access</p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  We&apos;re working with a small group of practices during EOFY 2026 to shape the product and the pricing.
                  Early partners get founder-friendly terms and direct input into the roadmap.
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-4 pt-8 border-t border-border">
              <Link
                href="/sign-up"
                className="group inline-flex items-center justify-center gap-3 px-8 py-4 bg-foreground hover:bg-foreground/90 text-background font-semibold rounded-full transition-all shadow-lg hover:shadow-xl"
              >
                Request Early Access
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <p className="text-sm text-muted-foreground">No credit card required. We&apos;ll reach out to discuss fit.</p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// CTA
// ============================================================================

function CTASection() {
  return (
    <section className="py-24 lg:py-32 bg-muted/30">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 text-center">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-light text-foreground leading-tight mb-6">
            EOFY is coming.<br />
            <span className="italic text-muted-foreground">Your new practice platform is ready.</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-xl mx-auto mb-10">
            Join the practices building their EOFY workflow on Clairo.
            BAS and tax planning modules are live. More shipping quarterly.
          </p>
          <Link
            href="/sign-up"
            className="group inline-flex items-center justify-center gap-3 px-10 py-5 bg-foreground hover:bg-foreground/90 text-background font-semibold text-lg rounded-full transition-all shadow-lg hover:shadow-xl"
          >
            Request Early Access
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </Link>
          <p className="mt-4 text-sm text-muted-foreground">No credit card required</p>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// FOOTER
// ============================================================================

function Footer() {
  return (
    <footer className="bg-card border-t border-border">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16">
        <div className="grid md:grid-cols-4 gap-12">
          <div className="md:col-span-2">
            <ClairoLogo size="lg" variant="light" className="dark:hidden mb-4" />
            <ClairoLogo size="lg" variant="dark" className="hidden dark:flex mb-4" />
            <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
              The AI practice platform for Australian accountants.
              Deep Xero integration. ATO-specific intelligence. Built to be the workhorse your practice deserves.
            </p>
          </div>

          <div>
            <p className="text-sm font-semibold text-foreground mb-4">Product</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><a href="#platform" className="hover:text-foreground transition-colors">Platform</a></li>
              <li><a href="#launching-with" className="hover:text-foreground transition-colors">BAS Workflow</a></li>
              <li><a href="#launching-with" className="hover:text-foreground transition-colors">Tax Planning</a></li>
              <li><a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a></li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-semibold text-foreground mb-4">Company</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/privacy" className="hover:text-foreground transition-colors">Privacy</Link></li>
              <li><Link href="/terms" className="hover:text-foreground transition-colors">Terms</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} Clairo. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="w-4 h-4 text-emerald-500" />
              <span>ATO Compliant</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Users className="w-4 h-4 text-blue-500" />
              <span>Australian Hosted</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ============================================================================
// MAIN PAGE
// ============================================================================

function TrendingUp(props: React.SVGProps<SVGSVGElement>) {
  return <LineChart {...props} />;
}

export default function HomePage() {
  return (
    <>
      <Header />
      <main>
        <HeroSection />
        <ProblemSection />
        <PlatformSection />
        <LaunchingWithSection />
        <HowItWorksSection />
        <ValueSection />
        <PricingSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
