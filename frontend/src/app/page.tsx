'use client';

import { motion, useScroll, useTransform } from 'framer-motion';
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Clock,
  Eye,
  Lightbulb,
  Scale,
  Shield,
  Target,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useRef } from 'react';

import { ClairoLogo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme';

// ============================================================================
// HEADER - Minimal, confident
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
            <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors font-medium">
              How It Works
            </a>
            <a href="#pillars" className="text-sm text-muted-foreground hover:text-foreground transition-colors font-medium">
              The Three Pillars
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
              Start Free Trial
            </Link>
          </div>
        </div>
      </nav>
    </motion.header>
  );
}

// ============================================================================
// HERO - Editorial, bold typography, asymmetric layout
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
      {/* Subtle texture background */}
      <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.05]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
      }} />

      <motion.div style={{ y, opacity }} className="relative z-10">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 pt-20 lg:pt-32">
          {/* Main Hero Content */}
          <div className="grid lg:grid-cols-12 gap-8 lg:gap-16 items-start">
            {/* Left Column - Headlines */}
            <div className="lg:col-span-7">
              {/* Badge */}
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

              {/* Main Headline - Editorial style */}
              <motion.h1
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.8 }}
                className="font-serif text-5xl sm:text-6xl lg:text-7xl xl:text-8xl font-light text-foreground leading-[0.95] tracking-tight mb-8"
              >
                See everything.
                <br />
                <span className="font-normal italic text-muted-foreground">Miss nothing.</span>
              </motion.h1>

              {/* Subheadline */}
              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="text-xl lg:text-2xl text-muted-foreground max-w-xl leading-relaxed mb-10 font-light"
              >
                The AI platform that transforms accountants into strategic advisors.
                Specialist AI agents. Real-time intelligence. Proactive insights for every client.
              </motion.p>

              {/* CTAs */}
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
                  Start Free Trial
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
                <a
                  href="#how-it-works"
                  className="inline-flex items-center justify-center gap-2 px-8 py-4 text-foreground font-semibold border-2 border-border hover:border-foreground/30 rounded-full transition-all"
                >
                  See How It Works
                </a>
              </motion.div>
            </div>

            {/* Right Column - The Command Center Card */}
            <motion.div
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, duration: 0.8 }}
              className="lg:col-span-5 lg:mt-8"
            >
              <CommandCenterCard />
            </motion.div>
          </div>

          {/* Scroll indicator */}
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

function CommandCenterCard() {
  return (
    <div className="relative">
      {/* Shadow/Depth effect */}
      <div className="absolute -inset-4 bg-gradient-to-br from-primary/10 to-status-warning/10 rounded-3xl blur-2xl" />

      {/* Main card */}
      <div className="relative bg-card border border-border rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-muted/50">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-400" />
            <div className="w-3 h-3 rounded-full bg-amber-400" />
            <div className="w-3 h-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-muted-foreground">Your Practice Dashboard</span>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Greeting */}
          <div className="mb-6">
            <p className="text-sm text-muted-foreground">Monday, 9:15 AM</p>
            <h3 className="text-lg font-semibold text-foreground">Good morning, Sarah</h3>
          </div>

          {/* Status Summary */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-status-danger">3</p>
              <p className="text-xs text-status-danger/70 font-medium">Urgent</p>
            </div>
            <div className="bg-status-warning/10 border border-status-warning/20 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-status-warning">7</p>
              <p className="text-xs text-status-warning/70 font-medium">Attention</p>
            </div>
            <div className="bg-status-success/10 border border-status-success/20 rounded-xl p-3 text-center">
              <p className="text-2xl font-bold text-status-success">40</p>
              <p className="text-xs text-status-success/70 font-medium">On Track</p>
            </div>
          </div>

          {/* AI Insight */}
          <div className="bg-status-info/10 border border-status-info/20 rounded-xl p-4 mb-4">
            <div className="flex items-start gap-3">
              <div className="p-1.5 bg-status-info/20 rounded-lg">
                <Lightbulb className="w-4 h-4 text-status-info" />
              </div>
              <div>
                <p className="text-sm font-medium text-status-info">AI Insight</p>
                <p className="text-xs text-status-info/80 mt-0.5">
                  3 clients approaching GST threshold this quarter. Registration options prepared.
                </p>
              </div>
            </div>
          </div>

          {/* Priority Item */}
          <div className="flex items-center gap-3 p-3 bg-muted rounded-xl">
            <div className="w-2 h-2 rounded-full bg-status-danger" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">Smith Plumbing</p>
              <p className="text-xs text-muted-foreground">ATO audit response due in 2 days</p>
            </div>
            <ArrowRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// PROBLEM STATEMENT - Bold, editorial
// ============================================================================

function ProblemSection() {
  return (
    <section className="py-24 lg:py-32 bg-card border-t border-border">
      <div className="max-w-5xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-6">
            You didn&apos;t become an accountant
            <br />
            <span className="text-muted-foreground">to check 50 Xero accounts every morning.</span>
          </h2>
        </motion.div>

        {/* The pain in numbers */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8"
        >
          <PainStat number="12+" unit="hours/week" label="Checking client status" />
          <PainStat number="50" unit="logins" label="Just to see what&apos;s urgent" />
          <PainStat number="$222" unit="per penalty" label="When something slips" />
          <PainStat number="0" unit="visibility" label="Into what you missed" />
        </motion.div>

        {/* The quote */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mt-20 text-center"
        >
          <blockquote className="relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 text-8xl text-border font-serif">&ldquo;</div>
            <p className="relative z-10 text-xl lg:text-2xl text-muted-foreground font-light italic max-w-3xl mx-auto leading-relaxed">
              Xero is great at helping each client run their business.
              <br />
              <span className="font-normal not-italic text-foreground">But who&apos;s helping you run your practice?</span>
            </p>
          </blockquote>
        </motion.div>
      </div>
    </section>
  );
}

function PainStat({ number, unit, label }: { number: string; unit: string; label: string }) {
  return (
    <div className="text-center p-6 lg:p-8 bg-muted rounded-2xl">
      <div className="flex items-baseline justify-center gap-1 mb-2">
        <span className="text-4xl lg:text-5xl font-light text-foreground">{number}</span>
        <span className="text-sm text-muted-foreground">{unit}</span>
      </div>
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

// ============================================================================
// HOW IT WORKS - The Transformation
// ============================================================================

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-24 lg:py-32 bg-background">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-4">
            Your AI Practice Partner
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Clairo doesn&apos;t wait for you to ask. It tells you what matters.
          </p>
        </motion.div>

        {/* Comparison */}
        <div className="grid lg:grid-cols-2 gap-8 lg:gap-12">
          {/* Traditional */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="bg-card border border-border rounded-2xl p-8 lg:p-10"
          >
            <div className="flex items-center gap-3 mb-8">
              <div className="p-2 bg-muted rounded-lg">
                <Clock className="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">Traditional Tools</h3>
                <p className="text-sm text-muted-foreground">Reactive. Manual. Fragmented.</p>
              </div>
            </div>

            <div className="space-y-4">
              <ComparisonItem text="You ask questions" negative />
              <ComparisonItem text="One perspective at a time" negative />
              <ComparisonItem text="Static dashboards" negative />
              <ComparisonItem text="Reactive compliance" negative />
              <ComparisonItem text="Data entry focus" negative />
              <ComparisonItem text="Tool for tasks" negative />
            </div>
          </motion.div>

          {/* Clairo */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="bg-gradient-to-br from-primary/10 to-status-warning/5 border border-primary/20 rounded-2xl p-8 lg:p-10"
          >
            <div className="flex items-center gap-3 mb-8">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Zap className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">With Clairo</h3>
                <p className="text-sm text-primary">Proactive. Intelligent. Unified.</p>
              </div>
            </div>

            <div className="space-y-4">
              <ComparisonItem text="AI tells you what matters" positive />
              <ComparisonItem text="Specialist AI agents collaborate" positive />
              <ComparisonItem text="Interfaces adapt to context" positive />
              <ComparisonItem text="Proactive intelligence" positive />
              <ComparisonItem text="Strategic advisory focus" positive />
              <ComparisonItem text="Partner for practice growth" positive />
            </div>
          </motion.div>
        </div>

        {/* Time Transformation */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8"
        >
          <div className="flex items-center gap-3 px-6 py-3 bg-card border border-border rounded-full">
            <Clock className="w-5 h-5 text-muted-foreground" />
            <span className="text-muted-foreground">4+ hours checking</span>
          </div>
          <ArrowRight className="w-6 h-6 text-primary rotate-90 sm:rotate-0" />
          <div className="flex items-center gap-3 px-6 py-3 bg-primary text-primary-foreground rounded-full shadow-lg">
            <Zap className="w-5 h-5" />
            <span className="font-semibold">30 minutes acting</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function ComparisonItem({ text, positive, negative }: { text: string; positive?: boolean; negative?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      {positive && <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0" />}
      {negative && <div className="w-5 h-5 rounded-full border-2 border-border flex-shrink-0" />}
      <span className={positive ? 'text-foreground' : 'text-muted-foreground'}>{text}</span>
    </div>
  );
}

// ============================================================================
// THREE PILLARS - The Foundation
// ============================================================================

function PillarsSection() {
  const pillars = [
    {
      icon: Eye,
      title: 'Data Intelligence',
      description: 'Complete financial picture from Xero. P&L, balance sheets, cash flow, fixed assets, receivables. Everything in one view.',
      features: ['Unified client view', 'Real-time sync', 'Pattern detection', 'Quality scoring'],
      color: 'blue' as const,
    },
    {
      icon: Shield,
      title: 'Compliance Mastery',
      description: 'ATO knowledge base with RAG technology. GST rules, BAS requirements, deadline monitoring, audit response assistance.',
      features: ['ATO correspondence parsing', 'Deadline extraction', 'Compliance alerts', 'Audit support'],
      color: 'emerald' as const,
    },
    {
      icon: TrendingUp,
      title: 'Strategic Advisory',
      description: 'Multi-perspective AI analysis. Tax optimization, business health assessment, growth planning, risk identification.',
      features: ['Tax planning insights', 'Structure optimization', 'Risk assessment', 'Options with trade-offs'],
      color: 'amber' as const,
    },
  ];

  const colorClasses = {
    blue: {
      bg: 'bg-status-info/10',
      border: 'border-status-info/20',
      icon: 'bg-status-info/20 text-status-info',
      dot: 'bg-status-info',
    },
    emerald: {
      bg: 'bg-status-success/10',
      border: 'border-status-success/20',
      icon: 'bg-status-success/20 text-status-success',
      dot: 'bg-status-success',
    },
    amber: {
      bg: 'bg-status-warning/10',
      border: 'border-status-warning/20',
      icon: 'bg-status-warning/20 text-status-warning',
      dot: 'bg-status-warning',
    },
  };

  return (
    <section id="pillars" className="py-24 lg:py-32 bg-card">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-4">
            Built on Three Pillars
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            When all three converge, Clairo delivers OPTIONS with trade-offs—not just recommendations.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-3 gap-8">
          {pillars.map((pillar, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className={`${colorClasses[pillar.color].bg} ${colorClasses[pillar.color].border} border rounded-2xl p-8`}
            >
              <div className={`inline-flex p-3 ${colorClasses[pillar.color].icon} rounded-xl mb-6`}>
                <pillar.icon className="w-6 h-6" />
              </div>

              <h3 className="text-xl font-semibold text-foreground mb-3">{pillar.title}</h3>
              <p className="text-muted-foreground mb-6 leading-relaxed">{pillar.description}</p>

              <ul className="space-y-3">
                {pillar.features.map((feature, i) => (
                  <li key={i} className="flex items-center gap-3 text-sm text-foreground">
                    <div className={`w-1.5 h-1.5 ${colorClasses[pillar.color].dot} rounded-full`} />
                    {feature}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// AI AGENTS - The Intelligence Layer
// ============================================================================

function AgentsSection() {
  const agents = [
    {
      name: 'Compliance',
      focus: 'ATO rules, BAS/GST, Deadlines',
      description: 'Monitors regulatory requirements and ensures nothing slips through.',
    },
    {
      name: 'Quality',
      focus: 'Data issues, Reconciliation, Missing info',
      description: 'Catches problems before they become costly mistakes.',
    },
    {
      name: 'Strategy',
      focus: 'Tax planning, Cash flow, Structure',
      description: 'Identifies optimization opportunities across your client base.',
    },
    {
      name: 'Insight',
      focus: 'Trends, Anomalies, Projections',
      description: 'Surfaces patterns you&apos;d never see manually.',
    },
  ];

  return (
    <section className="py-24 lg:py-32 bg-background overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-4">
            Specialist AI Agents.
            <br />
            <span className="text-muted-foreground">One Unified Answer.</span>
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            These agents don&apos;t just answer questions. They collaborate on complex scenarios and surface what matters before you even ask.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {agents.map((agent, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className="bg-card border border-border rounded-xl p-6 hover:border-foreground/20 transition-colors"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-primary to-primary/80 rounded-xl flex items-center justify-center mb-4 shadow-lg shadow-primary/20">
                <span className="text-white font-bold text-lg">{agent.name[0]}</span>
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-1">{agent.name}</h3>
              <p className="text-sm text-primary mb-3">{agent.focus}</p>
              <p className="text-sm text-muted-foreground">{agent.description}</p>
            </motion.div>
          ))}
        </div>

        {/* Magic Zone */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16 bg-gradient-to-r from-primary/10 via-card to-status-warning/10 border border-border rounded-2xl p-8 lg:p-10"
        >
          <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6 lg:gap-12">
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-foreground mb-2">The Magic Zone</h3>
              <p className="text-muted-foreground">
                When our agents converge on a client situation, Clairo presents OPTIONS with trade-offs—not just a single recommendation.
              </p>
            </div>
            <div className="flex-shrink-0 bg-muted border border-border rounded-xl p-4 w-full lg:w-auto">
              <p className="text-sm text-muted-foreground mb-3">&ldquo;Smith Plumbing approaching GST threshold...&rdquo;</p>
              <div className="flex gap-3">
                <div className="flex-1 bg-status-info/10 border border-status-info/20 rounded-lg p-2 text-center">
                  <p className="text-xs text-status-info font-medium">Option 1</p>
                  <p className="text-xs text-muted-foreground">Register Now</p>
                </div>
                <div className="flex-1 bg-status-warning/10 border border-status-warning/20 rounded-lg p-2 text-center">
                  <p className="text-xs text-status-warning font-medium">Option 2</p>
                  <p className="text-xs text-muted-foreground">Wait & Monitor</p>
                </div>
                <div className="flex-1 bg-status-success/10 border border-status-success/20 rounded-lg p-2 text-center">
                  <p className="text-xs text-status-success font-medium">Option 3</p>
                  <p className="text-xs text-muted-foreground">Review Structure</p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// VALUE PROPOSITION - Benefits
// ============================================================================

function ValueSection() {
  const values = [
    {
      icon: Clock,
      title: 'BAS prep in half the time',
      description: 'What took 4-6 hours now takes under 2.',
    },
    {
      icon: Target,
      title: 'Never miss a deadline',
      description: 'ATO correspondence parsed and tracked automatically.',
    },
    {
      icon: Lightbulb,
      title: 'Insights that write themselves',
      description: '5+ proactive insights per client, every week.',
    },
    {
      icon: Scale,
      title: 'Advice clients pay for',
      description: 'Move beyond compliance into strategic advisory.',
    },
    {
      icon: TrendingUp,
      title: 'Platform that gets smarter',
      description: 'Every interaction improves the AI for your practice.',
    },
  ];

  return (
    <section className="py-24 lg:py-32 bg-card">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-4">
            From Bookkeeper to Strategic Advisor
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            The transformation your practice has been waiting for.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-6">
          {values.map((value, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.05 }}
              className="bg-muted border border-border rounded-xl p-6 text-center"
            >
              <div className="inline-flex p-3 bg-background rounded-xl mb-4">
                <value.icon className="w-6 h-6 text-muted-foreground" />
              </div>
              <h3 className="text-sm font-semibold text-foreground mb-2">{value.title}</h3>
              <p className="text-sm text-muted-foreground">{value.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PRICING SECTION
// ============================================================================

function PricingSection() {
  const plans = [
    {
      name: 'Starter',
      price: '99',
      clients: '25 clients',
      description: 'For sole practitioners',
      features: ['Core BAS preparation', 'Xero sync', 'Basic AI insights', 'Email support'],
      highlight: false,
    },
    {
      name: 'Professional',
      price: '299',
      clients: '100 clients',
      description: 'For growing practices',
      features: ['Full AI advisory', 'Client portal', 'Proactive triggers', 'Karbon/XPM integration', 'Priority support'],
      highlight: true,
    },
    {
      name: 'Growth',
      price: '599',
      clients: '250 clients',
      description: 'For scaling practices',
      features: ['API access', 'Custom triggers', 'Advanced analytics', 'Dedicated support'],
      highlight: false,
    },
    {
      name: 'Enterprise',
      price: 'Custom',
      clients: 'Unlimited',
      description: 'For large practices',
      features: ['White-label option', 'SSO & security', 'Dedicated account manager', 'Custom integrations'],
      highlight: false,
    },
  ];

  return (
    <section id="pricing" className="py-24 lg:py-32 bg-background">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-4">
            Pricing That Scales With Your Practice
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Start free for 14 days. No credit card required.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {plans.map((plan, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className={`relative rounded-2xl p-6 ${
                plan.highlight
                  ? 'bg-foreground text-background shadow-xl'
                  : 'bg-card border border-border'
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-primary rounded-full text-xs font-semibold text-primary-foreground">
                  Most Popular
                </div>
              )}

              <div className="mb-6">
                <h3 className={`text-lg font-semibold ${plan.highlight ? 'text-background' : 'text-foreground'}`}>
                  {plan.name}
                </h3>
                <p className={`text-sm ${plan.highlight ? 'text-background/60' : 'text-muted-foreground'}`}>
                  {plan.description}
                </p>
              </div>

              <div className="mb-6">
                {plan.price === 'Custom' ? (
                  <p className={`text-3xl font-bold ${plan.highlight ? 'text-background' : 'text-foreground'}`}>Custom</p>
                ) : (
                  <div className="flex items-baseline gap-1">
                    <span className={`text-4xl font-bold ${plan.highlight ? 'text-background' : 'text-foreground'}`}>
                      ${plan.price}
                    </span>
                    <span className={plan.highlight ? 'text-background/60' : 'text-muted-foreground'}>/mo</span>
                  </div>
                )}
                <p className={`text-sm mt-1 ${plan.highlight ? 'text-primary-foreground/70' : 'text-primary'}`}>{plan.clients}</p>
              </div>

              <ul className="space-y-3 mb-6">
                {plan.features.map((feature, i) => (
                  <li key={i} className={`flex items-center gap-2 text-sm ${plan.highlight ? 'text-background/70' : 'text-muted-foreground'}`}>
                    <CheckCircle2 className={`w-4 h-4 flex-shrink-0 ${plan.highlight ? 'text-primary-foreground/70' : 'text-primary'}`} />
                    {feature}
                  </li>
                ))}
              </ul>

              <Link
                href="/sign-up"
                className={`block w-full py-3 text-center rounded-full font-semibold transition-colors ${
                  plan.highlight
                    ? 'bg-background text-foreground hover:bg-muted'
                    : 'bg-foreground text-background hover:bg-foreground/90'
                }`}
              >
                {plan.price === 'Custom' ? 'Contact Sales' : 'Start Free Trial'}
              </Link>
            </motion.div>
          ))}
        </div>

        {/* ROI Callout */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16 bg-card border border-border rounded-2xl p-8 lg:p-10"
        >
          <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6 lg:gap-12">
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-foreground mb-2">The Math Is Simple</h3>
              <p className="text-muted-foreground">
                If you manage 50 clients and spend 15 minutes per client per week just checking status—that&apos;s 12 hours.
                Every week. With Clairo, that&apos;s 30 minutes. At $200/hour, that&apos;s $2,300/week in time savings.
                We cost $299/month. <span className="font-semibold text-foreground">That&apos;s a 31x ROI.</span>
              </p>
            </div>
            <div className="flex-shrink-0 text-center lg:text-right">
              <p className="text-5xl font-bold text-primary">31x</p>
              <p className="text-sm text-muted-foreground">Return on Investment</p>
            </div>
          </div>
        </motion.div>

        {/* Guarantee */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-8 text-center"
        >
          <div className="inline-flex items-center gap-3 px-6 py-3 bg-status-success/10 border border-status-success/20 rounded-full">
            <Shield className="w-5 h-5 text-status-success" />
            <span className="text-sm text-status-success">
              <span className="font-semibold">30-day money-back guarantee.</span> If Clairo doesn&apos;t pay for itself, we&apos;ll refund you.
            </span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// SOCIAL PROOF
// ============================================================================

function SocialProofSection() {
  return (
    <section className="py-24 lg:py-32 bg-card border-y border-border">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl text-foreground mb-4">
            Trusted by Forward-Thinking Practices
          </h2>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-8 mb-16"
        >
          <div className="text-center">
            <p className="text-4xl lg:text-5xl font-light text-foreground">500+</p>
            <p className="text-sm text-muted-foreground mt-2">Practices</p>
          </div>
          <div className="text-center">
            <p className="text-4xl lg:text-5xl font-light text-foreground">50k+</p>
            <p className="text-sm text-muted-foreground mt-2">Clients Managed</p>
          </div>
          <div className="text-center">
            <p className="text-4xl lg:text-5xl font-light text-primary">99.8%</p>
            <p className="text-sm text-muted-foreground mt-2">On-Time Lodgement</p>
          </div>
          <div className="text-center">
            <p className="text-4xl lg:text-5xl font-light text-foreground">11.5</p>
            <p className="text-sm text-muted-foreground mt-2">Hours Saved/Week</p>
          </div>
        </motion.div>

        {/* Testimonials */}
        <div className="grid lg:grid-cols-3 gap-8">
          <TestimonialCard
            quote="I manage 67 clients. Before Clairo, Monday mornings were 4 hours of logging into Xero accounts. Now it's 15 minutes reviewing my priority queue."
            name="Sarah Mitchell"
            role="Principal"
            company="Mitchell & Associates, Sydney"
          />
          <TestimonialCard
            quote="An ATO audit notice sat buried in my inbox for almost a week. By the time I found it, I'd missed the response deadline. ATOtrack would have caught it day one."
            name="David Chen"
            role="Senior Accountant"
            company="Pacific Partners, Melbourne"
          />
          <TestimonialCard
            quote="The cross-client insights are gold. Clairo spotted three clients approaching GST threshold. My clients think I'm proactive. Really, it's the AI."
            name="Emma Thompson"
            role="Director"
            company="Thompson Advisory, Brisbane"
          />
        </div>
      </div>
    </section>
  );
}

function TestimonialCard({ quote, name, role, company }: { quote: string; name: string; role: string; company: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="bg-muted border border-border rounded-2xl p-8"
    >
      <div className="flex gap-1 mb-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="w-4 h-4 text-amber-400">
            <svg viewBox="0 0 20 20" fill="currentColor">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          </div>
        ))}
      </div>
      <p className="text-muted-foreground leading-relaxed mb-6">&ldquo;{quote}&rdquo;</p>
      <div className="border-t border-border pt-4">
        <p className="font-semibold text-foreground">{name}</p>
        <p className="text-sm text-muted-foreground">{role}</p>
        <p className="text-sm text-muted-foreground">{company}</p>
      </div>
    </motion.div>
  );
}

// ============================================================================
// FINAL CTA
// ============================================================================

function CTASection() {
  return (
    <section className="py-24 lg:py-32 bg-foreground text-background">
      <div className="max-w-4xl mx-auto px-6 lg:px-8 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="font-serif text-4xl sm:text-5xl lg:text-6xl text-white mb-6">
            Ready to See Everything?
          </h2>
          <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
            Join the accountants who&apos;ve stopped chasing data and started delivering value.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
            <Link
              href="/sign-up"
              className="group inline-flex items-center gap-3 px-8 py-4 bg-background text-foreground font-semibold rounded-full hover:bg-muted transition-all shadow-lg"
            >
              Start Your Free Trial
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          <p className="text-sm text-muted-foreground">
            No credit card required. Cancel anytime.
          </p>
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
    <footer className="bg-foreground text-background">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
          {/* Brand */}
          <div className="col-span-2">
            <Link href="/" className="flex items-center gap-3 mb-4">
              <ClairoLogo size="lg" variant="dark" />
            </Link>
            <p className="text-muted-foreground text-sm mb-4">
              See everything. Miss nothing.
            </p>
            <p className="text-muted-foreground text-sm">
              AI-powered practice intelligence for Australian accountants.
            </p>
          </div>

          {/* Product */}
          <div>
            <h4 className="font-semibold text-white mb-4">Product</h4>
            <ul className="space-y-3">
              {['Features', 'Pricing', 'Integrations', 'Security'].map((item) => (
                <li key={item}>
                  <a href="#" className="text-sm text-muted-foreground hover:text-white transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="font-semibold text-white mb-4">Resources</h4>
            <ul className="space-y-3">
              {['Documentation', 'Help Center', 'Blog', 'API'].map((item) => (
                <li key={item}>
                  <a href="#" className="text-sm text-muted-foreground hover:text-white transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="font-semibold text-white mb-4">Company</h4>
            <ul className="space-y-3">
              {['About', 'Contact', 'Privacy', 'Terms'].map((item) => (
                <li key={item}>
                  <a href="#" className="text-sm text-muted-foreground hover:text-white transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-background/20 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} Clairo. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="w-4 h-4 text-status-success" />
              <span>ATO Compliant</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Users className="w-4 h-4 text-status-info" />
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

export default function HomePage() {
  return (
    <>
      <Header />
      <main>
        <HeroSection />
        <ProblemSection />
        <HowItWorksSection />
        <PillarsSection />
        <AgentsSection />
        <ValueSection />
        <PricingSection />
        <SocialProofSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
