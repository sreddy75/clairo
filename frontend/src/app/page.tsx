'use client';

import { motion, useScroll, useTransform, useMotionValue, useSpring, animate } from 'framer-motion';
import {
  ArrowRight,
  ChevronDown,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import { ClairoLogo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme';

// ============================================================================
// ANIMATED COUNTER — counts up on mount
// ============================================================================

function AnimatedNumber({ value, duration = 2, suffix = '' }: { value: number; duration?: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(0);

  useEffect(() => {
    if (value === prevValue.current) return;
    const from = prevValue.current;
    prevValue.current = value;
    const controls = animate(from, value, {
      duration: from === 0 ? duration : 0.8,
      ease: 'easeOut',
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [value, duration]);

  return <span>{display}{suffix}</span>;
}

// ============================================================================
// HEADER — Understated, professional
// ============================================================================

function Header() {
  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6 }}
      className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border/40"
    >
      <nav className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <div className="flex h-14 items-center justify-between">
          <Link href="/" className="flex items-center">
            <ClairoLogo size="lg" variant="light" className="dark:hidden" />
            <ClairoLogo size="lg" variant="dark" className="hidden dark:flex" />
          </Link>

          <div className="hidden md:flex items-center gap-8">
            {['Platform', 'Modules', 'How It Works', 'Pricing'].map((label) => (
              <a
                key={label}
                href={`#${label.toLowerCase().replace(/ /g, '-')}`}
                className="text-[13px] text-muted-foreground hover:text-foreground transition-colors tracking-wide uppercase"
              >
                {label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/sign-in"
              className="text-[13px] text-muted-foreground hover:text-foreground transition-colors tracking-wide"
            >
              Sign In
            </Link>
            <Link
              href="/sign-up"
              className="px-5 py-2 text-[13px] font-medium tracking-wide text-primary-foreground bg-primary hover:bg-primary/90 rounded-md transition-all"
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
// HERO — Editorial typographic impact + live data visualization
// ============================================================================

function usePlatformStats() {
  const [stats, setStats] = useState({ clients_managed: 0, practices: 0, tax_plans: 0, bas_generated: 0, scenarios_modelled: 0 });

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
    fetch(`${apiUrl}/api/v1/public/stats`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (data && typeof data.clients_managed === 'number') {
          setStats(data);
        }
      })
      .catch(() => {});
  }, []);

  return stats;
}

function PracticeVisualization() {
  const stats = usePlatformStats();
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 50, damping: 20 });

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    mouseX.set((e.clientX - rect.left - rect.width / 2) * 0.02);
    mouseY.set((e.clientY - rect.top - rect.height / 2) * 0.02);
  };

  // Generate dots based on real client count (min 8 for visual density)
  const dotCount = Math.max(stats.clients_managed, 8);
  const displayCount = Math.min(dotCount, 40); // cap visual dots
  const clients = Array.from({ length: displayCount }, (_, i) => {
    // Deterministic pseudo-random distribution using golden angle
    const angle = i * 137.508 * (Math.PI / 180);
    const radius = 12 + (i / displayCount) * 35;
    const x = 50 + Math.cos(angle) * radius + ((i * 7) % 11) - 5;
    const y = 50 + Math.sin(angle) * radius + ((i * 13) % 9) - 4;
    const status = i === 0 ? 'urgent' : i < 3 ? 'attention' : 'good';
    return {
      x: Math.max(5, Math.min(95, x)),
      y: Math.max(5, Math.min(95, y)),
      status,
      size: 5 + (i % 4) * 2,
      label: i === 0 ? 'BAS Overdue' : i === 1 ? 'Attention' : '',
    };
  });

  const statusColor = (s: string) =>
    s === 'urgent' ? 'hsl(var(--status-danger))' :
    s === 'attention' ? 'hsl(var(--status-warning))' :
    'hsl(var(--status-success))';

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      className="relative w-full aspect-square max-w-md mx-auto"
      style={{ x: springX, y: springY }}
    >
      {/* Outer ring */}
      <div className="absolute inset-0 rounded-full border border-border/30" />
      <div className="absolute inset-4 rounded-full border border-border/20" />
      <div className="absolute inset-8 rounded-full border border-border/10" />

      {/* Client dots */}
      {clients.map((client, i) => (
        <motion.div
          key={i}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.8 + i * 0.06, type: 'spring', stiffness: 200 }}
          className="absolute group"
          style={{
            left: `${client.x}%`,
            top: `${client.y}%`,
            transform: 'translate(-50%, -50%)',
          }}
        >
          {/* Pulse ring for urgent/attention */}
          {client.status !== 'good' && (
            <motion.div
              animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
              transition={{ repeat: Infinity, duration: 2, delay: i * 0.3 }}
              className="absolute inset-0 rounded-full"
              style={{
                backgroundColor: statusColor(client.status),
                width: client.size,
                height: client.size,
              }}
            />
          )}
          <div
            className="rounded-full relative"
            style={{
              width: client.size,
              height: client.size,
              backgroundColor: statusColor(client.status),
              boxShadow: `0 0 ${client.size * 2}px ${statusColor(client.status)}40`,
            }}
          />
          {client.label && (
            <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-[10px] font-medium text-muted-foreground bg-card/90 backdrop-blur-sm px-2 py-0.5 rounded border border-border/50">
                {client.label}
              </span>
            </div>
          )}
        </motion.div>
      ))}

      {/* Center metrics */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.2 }}
          className="text-center space-y-5"
        >
          <div>
            <p className="text-8xl font-light text-foreground tabular-nums">
              <AnimatedNumber value={stats.clients_managed} />
            </p>
            <p className="text-[11px] text-muted-foreground uppercase tracking-[0.2em] mt-1">Clients</p>
          </div>
          <div className="flex items-center gap-10">
            <div className="text-center">
              <p className="text-5xl font-light text-foreground tabular-nums">
                <AnimatedNumber value={stats.bas_generated} />
              </p>
              <p className="text-[10px] text-muted-foreground uppercase tracking-[0.15em]">BAS Prepared</p>
            </div>
            <div className="w-px h-12 bg-border/40" />
            <div className="text-center">
              <p className="text-5xl font-light text-foreground tabular-nums">
                <AnimatedNumber value={stats.tax_plans} />
              </p>
              <p className="text-[10px] text-muted-foreground uppercase tracking-[0.15em]">Tax Plans</p>
            </div>
            <div className="w-px h-12 bg-border/40" />
            <div className="text-center">
              <p className="text-5xl font-light text-foreground tabular-nums">
                <AnimatedNumber value={stats.scenarios_modelled} />
              </p>
              <p className="text-[10px] text-muted-foreground uppercase tracking-[0.15em]">Tax Scenarios Generated</p>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

function HeroSection() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end start'],
  });
  const y = useTransform(scrollYProgress, [0, 1], [0, 150]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <section ref={ref} className="relative min-h-screen bg-background overflow-hidden pt-14">
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-[0.03] dark:opacity-[0.06]"
        style={{
          backgroundImage: `
            linear-gradient(hsl(var(--border)) 1px, transparent 1px),
            linear-gradient(90deg, hsl(var(--border)) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />

      <motion.div style={{ y, opacity }} className="relative z-10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12 pt-16 lg:pt-24">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-8 items-center min-h-[calc(100vh-8rem)]">
            {/* Left — Copy */}
            <div>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="text-[11px] font-medium text-primary uppercase tracking-[0.3em] mb-10"
              >
                For Australian Accounting Practices
              </motion.p>

              <motion.h1
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.8 }}
                className="text-[clamp(3rem,7vw,6.5rem)] font-light text-foreground leading-[0.9] tracking-[-0.03em] mb-8"
                style={{ fontFamily: 'var(--font-heading)' }}
              >
                Your expertise.
                <br />
                <span className="text-muted-foreground/60">Every client. Every time.</span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="text-lg text-muted-foreground max-w-lg leading-relaxed mb-10"
              >
                Clairo pulls your Xero data, evaluates 20+ tax strategies against ATO
                rulings, and generates a complete tax plan with real numbers — in minutes,
                not hours. You review, approve, and share. EOFY sorted.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="flex flex-col sm:flex-row gap-4"
              >
                <Link
                  href="/sign-up"
                  className="group inline-flex items-center justify-center gap-3 px-7 py-3.5 bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-md transition-all text-sm tracking-wide"
                >
                  Request Early Access
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Link>
                <a
                  href="#platform"
                  className="inline-flex items-center justify-center gap-2 px-7 py-3.5 text-foreground font-medium border border-border hover:border-foreground/30 rounded-md transition-all text-sm tracking-wide"
                >
                  See the Platform
                </a>
              </motion.div>
            </div>

            {/* Right — Practice constellation visualization */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6, duration: 1 }}
              className="hidden lg:block"
            >
              <PracticeVisualization />
            </motion.div>
          </div>

          {/* Scroll indicator */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.5 }}
            className="absolute bottom-6 left-1/2 -translate-x-1/2"
          >
            <motion.div
              animate={{ y: [0, 6, 0] }}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              <ChevronDown className="w-5 h-5 text-muted-foreground/40" />
            </motion.div>
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}

// ============================================================================
// PROBLEM — Asymmetric editorial layout
// ============================================================================

function ProblemSection() {
  return (
    <section className="py-28 lg:py-40 border-t border-border/40">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-12 gap-12 lg:gap-20">
          {/* Left — Statement */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="lg:col-span-5"
          >
            <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-foreground leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: 'var(--font-heading)' }}>
              Your practice runs on a&nbsp;dozen tools that don&apos;t talk to each&nbsp;other.
            </h2>
            <p className="text-muted-foreground leading-relaxed">
              You&apos;re logging into Xero to check numbers, switching to a spreadsheet to run tax scenarios,
              chasing clients for documents over email, and hoping nothing falls through the cracks.
              Every practice runs this way. None of them should have to.
            </p>
          </motion.div>

          {/* Right — Stats in a ledger-style grid */}
          <div className="lg:col-span-7 lg:col-start-7">
            <div className="grid grid-cols-2 border-l border-t border-border/60">
              {[
                { value: 12, suffix: '+', unit: 'hrs/week', label: 'Checking client status across tools' },
                { value: 50, suffix: '', unit: 'logins', label: 'Just to see what needs attention today' },
                { value: 30, suffix: '', unit: 'min/client', label: 'To manually pull and format tax data' },
                { value: 0, suffix: '', unit: 'visibility', label: 'Into what you missed last quarter' },
              ].map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="border-r border-b border-border/60 p-6 lg:p-8"
                >
                  <div className="flex items-baseline gap-1.5 mb-1">
                    <span className="text-3xl lg:text-4xl font-light text-foreground tabular-nums">
                      <AnimatedNumber value={item.value} suffix={item.suffix} />
                    </span>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">{item.unit}</span>
                  </div>
                  <p className="text-sm text-muted-foreground/70 leading-snug">{item.label}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PLATFORM — Three pillars with distinct visual treatment
// ============================================================================

function PlatformSection() {
  return (
    <section id="platform" className="py-28 lg:py-40 bg-foreground text-background">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl mb-20"
        >
          <p className="text-[11px] font-medium text-primary uppercase tracking-[0.3em] mb-6">The Platform</p>
          <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: 'var(--font-heading)' }}>
            One platform. Every workflow.
          </h2>
          <p className="text-background/60 leading-relaxed">
            Clairo is a practice intelligence platform that connects your Xero data to AI trained on Australian tax law.
            Each module tackles a different part of your workflow — BAS, tax planning, client management, and more as the platform grows.
            You&apos;re not buying a point solution. You&apos;re buying into a workhorse that gets more capable every quarter.
          </p>
        </motion.div>

        {/* Three pillars — horizontal accordion style */}
        <div className="grid lg:grid-cols-3 gap-px bg-background/10 rounded-lg overflow-hidden">
          {[
            {
              number: '01',
              title: 'Deep Xero Integration',
              detail: 'We sync everything — P&L, balance sheets, bank transactions, credit notes, journals, fixed assets, payments, purchase orders. Not just invoices. Everything.',
              stat: '30+',
              statLabel: 'entity types synced',
            },
            {
              number: '02',
              title: 'ATO-Trained AI',
              detail: 'Our knowledge base ingests ATO rulings, legislation, case law, and tax rates. When the AI advises on a scenario, it cites the relevant provision — not a hallucinated one.',
              stat: '6',
              statLabel: 'specialist scrapers',
            },
            {
              number: '03',
              title: 'Specialist AI Agents',
              detail: 'Multiple AI agents analyse each situation from different angles — compliance, quality, cash flow, strategy. When they converge, you get options with trade-offs, not just a single answer.',
              stat: '4',
              statLabel: 'agent perspectives',
            },
          ].map((pillar, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              className="bg-foreground p-8 lg:p-10 flex flex-col justify-between min-h-[320px]"
            >
              <div>
                <p className="text-background/20 text-sm font-medium mb-4 tracking-wider">{pillar.number}</p>
                <h3 className="text-xl font-medium text-background mb-4" style={{ fontFamily: 'var(--font-heading)' }}>{pillar.title}</h3>
                <p className="text-background/50 text-sm leading-relaxed">{pillar.detail}</p>
              </div>
              <div className="mt-8 pt-6 border-t border-background/10">
                <span className="text-3xl font-light text-primary tabular-nums">{pillar.stat}</span>
                <span className="text-xs text-background/40 uppercase tracking-wider ml-2">{pillar.statLabel}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// LAUNCHING WITH — BAS + Tax Planning (the first two modules)
// ============================================================================

function LaunchingWithSection() {
  return (
    <section id="modules" className="py-28 lg:py-40 border-t border-border/40">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl mb-20"
        >
          <p className="text-[11px] font-medium text-primary uppercase tracking-[0.3em] mb-6">First off the rank</p>
          <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-foreground leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: 'var(--font-heading)' }}>
            BAS workflow and AI tax planning — ready for EOFY.
          </h2>
          <p className="text-muted-foreground leading-relaxed">
            We&apos;re launching with the two workflows every practice runs during April–June.
            These are production-ready today, with more modules shipping quarterly.
          </p>
        </motion.div>

        {/* Two modules — asymmetric layout */}
        <div className="space-y-1">
          {/* BAS Module */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="grid lg:grid-cols-12 gap-8 bg-card rounded-lg border border-border/60 p-8 lg:p-10"
          >
            <div className="lg:col-span-4">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-2 h-8 rounded-full bg-blue-500" />
                <div>
                  <h3 className="text-lg font-medium text-foreground" style={{ fontFamily: 'var(--font-heading)' }}>End-to-End BAS</h3>
                  <p className="text-xs text-muted-foreground tracking-wide">Compliance workflow</p>
                </div>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Pull financials from Xero, calculate BAS fields, resolve unmapped tax codes with AI suggestions,
                and track every change in a tamper-evident audit trail. Your clients classify their own uncertain transactions
                via a magic link — no chasing.
              </p>
            </div>
            <div className="lg:col-span-8 lg:col-start-6 grid sm:grid-cols-2 gap-4">
              {[
                'AI resolves unmapped tax codes (NONE, BASEXCLUDED) with confidence tiers',
                'Client portal — business owners classify transactions via magic link',
                'Full BAS field calculation with variance analysis',
                'Audit trail satisfies ATO 7-year retention requirements',
                'Data quality scoring flags issues before you start',
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-1 h-1 rounded-full bg-blue-500 mt-2 shrink-0" />
                  <span className="text-sm text-muted-foreground leading-snug">{item}</span>
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
            className="grid lg:grid-cols-12 gap-8 bg-card rounded-lg border border-border/60 p-8 lg:p-10"
          >
            <div className="lg:col-span-4">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-2 h-8 rounded-full bg-emerald-500" />
                <div>
                  <h3 className="text-lg font-medium text-foreground" style={{ fontFamily: 'var(--font-heading)' }}>AI Tax Planning</h3>
                  <p className="text-xs text-muted-foreground tracking-wide">Advisory workflow</p>
                </div>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Pull a client&apos;s P&L and bank balances from Xero, see their estimated tax position in seconds,
                then describe a scenario in plain English and let the AI model strategies with real numbers, compliance notes,
                and risk ratings.
              </p>
            </div>
            <div className="lg:col-span-8 lg:col-start-6 grid sm:grid-cols-2 gap-4">
              {[
                'Xero P&L auto-pulled with bank balances and reconciliation status',
                'Accurate tax calculations — company, individual, trust, partnership',
                'AI scenario modelling: "what if we prepay $30K rent before June 30?"',
                'Each scenario shows tax saving, cash flow impact, and ATO risk rating',
                'Export client-ready PDF with practice branding and disclaimers',
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-1 h-1 rounded-full bg-emerald-500 mt-2 shrink-0" />
                  <span className="text-sm text-muted-foreground leading-snug">{item}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Coming next — minimal, suggestive */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="mt-16 flex flex-wrap gap-x-8 gap-y-3 text-sm text-muted-foreground/50"
        >
          <span className="text-xs text-muted-foreground uppercase tracking-[0.2em]">Coming next</span>
          <span className="border-b border-dashed border-muted-foreground/20 pb-0.5">ATO Correspondence Tracking</span>
          <span className="border-b border-dashed border-muted-foreground/20 pb-0.5">Cash Flow Forecasting</span>
          <span className="border-b border-dashed border-muted-foreground/20 pb-0.5">Multi-Entity Groups</span>
          <span className="border-b border-dashed border-muted-foreground/20 pb-0.5">Voice Feedback Portal</span>
        </motion.div>
      </div>
    </section>
  );
}

// ============================================================================
// HOW IT WORKS — Horizontal numbered flow
// ============================================================================

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-28 lg:py-40 bg-muted/40 border-t border-border/40">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="mb-20"
        >
          <p className="text-[11px] font-medium text-primary uppercase tracking-[0.3em] mb-6">How It Works</p>
          <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-foreground leading-[1.1] tracking-[-0.02em]" style={{ fontFamily: 'var(--font-heading)' }}>
            Connect once. Clairo does the rest.
          </h2>
        </motion.div>

        <div className="grid lg:grid-cols-3 gap-16">
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
            >
              <p className="text-6xl lg:text-7xl font-light text-border/80 dark:text-border/40 mb-6 tabular-nums">{item.step}</p>
              <h3 className="text-lg font-medium text-foreground mb-3" style={{ fontFamily: 'var(--font-heading)' }}>{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// VALUE — Alternating layout, no card grid
// ============================================================================

function ValueSection() {
  const values = [
    {
      title: 'From data entry to advisory',
      desc: 'Stop typing numbers from Xero into spreadsheets. Start modelling tax strategies with AI that knows the ATO rules.',
    },
    {
      title: 'Clients in the loop',
      desc: 'Business owners classify their own transactions, upload documents, and leave voice feedback — all through a simple portal.',
    },
    {
      title: 'Nothing slips through',
      desc: 'AI agents scan your portfolio daily. Unmapped tax codes, quality issues, and approaching thresholds are surfaced before they become problems.',
    },
    {
      title: 'Compliance you can trust',
      desc: 'Every AI suggestion requires your approval. Every change is audit-logged. The AI assists — you decide.',
    },
    {
      title: 'Platform that grows with you',
      desc: 'BAS and tax planning are the first modules. New capabilities ship quarterly. Your subscription gets more valuable over time, not more expensive.',
    },
    {
      title: 'Built for Australian practices',
      desc: 'GST, BAS, PAYG, FBT, Division 7A, Part IVA — the AI speaks your language because it was trained on your domain.',
    },
  ];

  return (
    <section className="py-28 lg:py-40 border-t border-border/40">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl mb-20"
        >
          <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-foreground leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: 'var(--font-heading)' }}>
            Fair value for your practice and your clients.
          </h2>
          <p className="text-muted-foreground leading-relaxed">
            Clairo doesn&apos;t just save you time. It elevates the quality of service your clients receive
            — more accurate BAS, proactive tax advice, and a portal where they can participate in the process.
          </p>
        </motion.div>

        {/* Two-column flowing list instead of card grid */}
        <div className="grid lg:grid-cols-2 gap-x-20 gap-y-12">
          {values.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: (i % 2) * 0.1 }}
              className="flex gap-5"
            >
              <div className="shrink-0 w-8 text-right">
                <span className="text-xs text-muted-foreground/40 tabular-nums">{String(i + 1).padStart(2, '0')}</span>
              </div>
              <div className="border-t border-border/60 pt-4 flex-1">
                <h3 className="text-base font-medium text-foreground mb-2" style={{ fontFamily: 'var(--font-heading)' }}>{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
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
    <section id="pricing" className="py-28 lg:py-40 bg-muted/40 border-t border-border/40">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-12 gap-12 lg:gap-20">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="lg:col-span-5"
          >
            <p className="text-[11px] font-medium text-primary uppercase tracking-[0.3em] mb-6">Pricing</p>
            <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-foreground leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: 'var(--font-heading)' }}>
              Pricing that reflects results, not seats.
            </h2>
            <p className="text-muted-foreground leading-relaxed mb-8">
              We don&apos;t think you should pay more because you have more logins.
              You should pay based on the value you get — the clients you serve, the work Clairo handles for you.
              We&apos;re finalising our pricing model with early access partners now.
            </p>
            <Link
              href="/sign-up"
              className="group inline-flex items-center justify-center gap-3 px-7 py-3.5 bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-md transition-all text-sm tracking-wide"
            >
              Request Early Access
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <p className="text-xs text-muted-foreground mt-3">No credit card required</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2, duration: 0.8 }}
            className="lg:col-span-6 lg:col-start-7"
          >
            <div className="space-y-8">
              <div>
                <p className="text-xs font-medium text-foreground uppercase tracking-[0.2em] mb-4">What you get</p>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    'Full platform access',
                    'BAS + Tax Planning modules',
                    'Deep Xero integration',
                    'ATO knowledge base',
                    'Client portal',
                    'New modules as they ship',
                  ].map((item, i) => (
                    <p key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                      <span className="w-1 h-1 rounded-full bg-primary shrink-0" />
                      {item}
                    </p>
                  ))}
                </div>
              </div>

              <div className="border-t border-border/60 pt-8">
                <p className="text-xs font-medium text-foreground uppercase tracking-[0.2em] mb-4">How we price</p>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    'Based on clients managed',
                    'Not per seat or per login',
                    'No lock-in contracts',
                    'Free onboarding support',
                  ].map((item, i) => (
                    <p key={i} className="text-sm text-muted-foreground flex items-center gap-2">
                      <span className="w-1 h-1 rounded-full bg-primary shrink-0" />
                      {item}
                    </p>
                  ))}
                </div>
              </div>

              <div className="border-t border-border/60 pt-8">
                <p className="text-xs font-medium text-foreground uppercase tracking-[0.2em] mb-4">Early access</p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  We&apos;re working with a small group of practices during EOFY 2026 to shape the product and the pricing.
                  Early partners get founder-friendly terms and direct input into the roadmap.
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// CTA
// ============================================================================

function CTASection() {
  return (
    <section className="py-28 lg:py-40 border-t border-border/40">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 text-center">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl mx-auto"
        >
          <h2 className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-foreground leading-[1.1] tracking-[-0.02em] mb-4" style={{ fontFamily: 'var(--font-heading)' }}>
            EOFY is coming.
          </h2>
          <p className="text-[clamp(1.8rem,4vw,3.2rem)] font-light text-muted-foreground/50 leading-[1.1] tracking-[-0.02em] mb-10" style={{ fontFamily: 'var(--font-heading)' }}>
            Your new practice platform is ready.
          </p>
          <p className="text-muted-foreground mb-10">
            Join the practices building their EOFY workflow on Clairo.
            BAS and tax planning modules are live. More shipping quarterly.
          </p>
          <Link
            href="/sign-up"
            className="group inline-flex items-center justify-center gap-3 px-8 py-4 bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-md transition-all text-sm tracking-wide"
          >
            Request Early Access
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Link>
          <p className="mt-4 text-xs text-muted-foreground">No credit card required</p>
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
    <footer className="border-t border-border/40 bg-card">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-16">
        <div className="grid md:grid-cols-12 gap-12">
          <div className="md:col-span-5">
            <ClairoLogo size="lg" variant="light" className="dark:hidden mb-4" />
            <ClairoLogo size="lg" variant="dark" className="hidden dark:flex mb-4" />
            <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
              The AI practice platform for Australian accountants.
              Deep Xero integration. ATO-specific intelligence.
            </p>
          </div>

          <div className="md:col-span-3 md:col-start-7">
            <p className="text-xs font-medium text-foreground uppercase tracking-[0.2em] mb-4">Product</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><a href="#platform" className="hover:text-foreground transition-colors">Platform</a></li>
              <li><a href="#modules" className="hover:text-foreground transition-colors">BAS Workflow</a></li>
              <li><a href="#modules" className="hover:text-foreground transition-colors">Tax Planning</a></li>
              <li><a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a></li>
            </ul>
          </div>

          <div className="md:col-span-2">
            <p className="text-xs font-medium text-foreground uppercase tracking-[0.2em] mb-4">Company</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/privacy" className="hover:text-foreground transition-colors">Privacy</Link></li>
              <li><Link href="/terms" className="hover:text-foreground transition-colors">Terms</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-16 pt-8 border-t border-border/40 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} Clairo. All rights reserved.
          </p>
          <div className="flex items-center gap-6 text-xs text-muted-foreground">
            <span>ATO Compliant</span>
            <span className="w-px h-3 bg-border" />
            <span>Australian Hosted</span>
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
