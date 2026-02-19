import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useMotionValue, useTransform } from 'framer-motion';
import {
    Terminal, GitBranch, CheckCircle, AlertOctagon,
    Activity, Clock, Shield, Cpu,
    Zap, FileCode, Check, Command, Users, User
} from 'lucide-react';
import { ParticleWave } from '../components/ParticleWave';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useHealStore } from '../stores/useHealStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { startHeal } from '../lib/api';
import type { FixEntry } from '../types';

function cn(...inputs: (string | undefined | null | false)[]) {
    return twMerge(clsx(inputs));
}

// ── Pipeline steps matching backend nodes ──
const PIPELINE_STEPS = [
    "Cloning & analyzing repository...",
    "Running test suite...",
    "Classifying failures...",
    "Generating AI fixes...",
    "Validating & applying patches...",
    "Committing changes...",
    "Monitoring CI/CD pipeline...",
    "Calculating final score...",
];

const PIPELINE_NODES = [
    "repo_analyzer",
    "test_runner",
    "bug_classifier",
    "fix_generator",
    "fix_validator",
    "git_ops",
    "ci_monitor",
    "scorer",
];

// ── Bug type color map for dark theme ──
const BUG_TYPE_BADGE: Record<string, string> = {
    LINTING: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    SYNTAX: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    LOGIC: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    TYPE_ERROR: "bg-red-500/10 text-red-400 border-red-500/20",
    IMPORT: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    INDENTATION: "bg-teal-500/10 text-teal-400 border-teal-500/20",
};

// ── Sub-components ──

const Navbar = () => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const user = useHealStore((s) => s.user);
    const logout = useHealStore((s) => s.logout);

    return (
        <nav className="sticky top-4 z-50 mx-auto max-w-5xl">
            <div className="flex items-center border mx-4 max-md:w-full max-md:justify-between border-white/20 bg-[#F0EBE3]/10 backdrop-blur-xl px-6 py-4 rounded-full text-stone-200 text-sm shadow-2xl relative ring-1 ring-white/10 before:absolute before:inset-0 before:bg-gradient-to-b before:from-white/10 before:to-transparent before:rounded-full before:pointer-events-none">
                <a href="/">
                    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="opacity-90 hover:opacity-100 transition-opacity">
                        <circle cx="4.706" cy="16" r="4.706" fill="#F0EBE3" />
                        <circle cx="16.001" cy="4.706" r="4.706" fill="#F0EBE3" />
                        <circle cx="16.001" cy="27.294" r="4.706" fill="#F0EBE3" />
                        <circle cx="27.294" cy="16" r="4.706" fill="#F0EBE3" />
                    </svg>
                </a>
                <div className="hidden md:flex items-center gap-8 ml-10 font-medium z-10">
                    {['Activity', 'Docs'].map((item) => (
                        <a key={item} href="#" className="relative overflow-hidden h-[18px] group text-stone-300 hover:text-emerald-400 transition-colors">
                            <span className="block group-hover:-translate-y-full transition-transform duration-300">{item}</span>
                            <span className="block absolute top-full left-0 group-hover:translate-y-[-100%] transition-transform duration-300">{item}</span>
                        </a>
                    ))}
                </div>
                <div className="hidden ml-auto md:flex items-center gap-4 z-10">
                    <div onClick={logout} className="flex items-center gap-3 pl-3 pr-1 py-1 bg-white/5 border border-white/10 rounded-full hover:bg-white/10 transition-colors cursor-pointer group shadow-sm backdrop-blur-md" title="Click to logout">
                        <div className="flex flex-col items-end">
                            <span className="text-xs font-bold text-stone-200 leading-none group-hover:text-emerald-400 transition-colors">{user?.name || user?.login || 'CI Heal Agent'}</span>
                            <span className="text-[10px] text-stone-500 font-mono leading-none mt-1">@{user?.login || 'debugit'}</span>
                        </div>
                        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-emerald-400 to-teal-400 p-[1.5px] shadow-lg shadow-emerald-500/20">
                            <img src={user?.avatar_url || 'https://github.com/ghost.png'} alt="Profile" className="w-full h-full rounded-full bg-[#1c1917] object-cover" />
                        </div>
                    </div>
                </div>
                <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="md:hidden text-stone-400 hover:text-white transition-colors z-10">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </button>
                {isMobileMenuOpen && (
                    <div className="absolute top-full left-0 mt-2 bg-[#1c1917]/90 backdrop-blur-xl border border-white/10 w-full flex flex-col items-center gap-4 py-6 rounded-3xl shadow-2xl md:hidden z-50">
                        <a className="hover:text-emerald-400 transition-colors font-medium text-stone-300" href="#">Activity</a>
                        <a className="hover:text-emerald-400 transition-colors font-medium text-stone-300" href="#">Docs</a>
                    </div>
                )}
            </div>
        </nav>
    );
};

const MetricsCard = ({ label, value, trend, icon: Icon, delay }: { label: string; value: string; trend?: string; icon: React.ComponentType<{ className?: string }>; delay: number }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay }}
        className="bg-white/5 border border-white/10 p-5 rounded-2xl shadow-lg backdrop-blur-md hover:bg-white/10 hover:border-emerald-500/30 hover:shadow-emerald-500/10 hover:-translate-y-1 transition-all duration-300 group cursor-default relative overflow-hidden ring-1 ring-white/5"
    >
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-[60px] -translate-y-1/2 translate-x-1/2 group-hover:bg-emerald-500/20 transition-colors duration-500" />
        <div className="flex justify-between items-start mb-3 relative z-10">
            <span className="text-stone-400 text-xs font-bold uppercase tracking-wider">{label}</span>
            <div className="bg-white/5 p-2 rounded-xl group-hover:bg-emerald-500/20 group-hover:text-emerald-400 transition-colors duration-300 shadow-sm border border-white/5">
                <Icon className="w-4 h-4 text-stone-500 group-hover:text-emerald-400 transition-colors" />
            </div>
        </div>
        <div className="flex items-end gap-3 relative z-10">
            <span className="text-3xl font-display font-bold text-stone-100 tracking-tight">{value}</span>
            {trend && (
                <div className="text-xs px-2 py-0.5 rounded-full mb-1.5 font-bold flex items-center gap-1 backdrop-blur-sm bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {trend}
                </div>
            )}
        </div>
    </motion.div>
);

const StepItem = ({ step, currentStep, index }: { step: string; currentStep: number; index: number }) => {
    const isCompleted = index < currentStep;
    const isCurrent = index === currentStep;

    return (
        <div className="relative pl-8 pb-8 last:pb-0 group">
            {index !== PIPELINE_STEPS.length - 1 && (
                <div className={cn("absolute left-3 top-8 w-[2px] h-[calc(100%-8px)] rounded-full", isCompleted ? "bg-emerald-500/50" : "bg-white/10")} />
            )}
            <div className={cn(
                "absolute left-0 top-1 w-6 h-6 rounded-full flex items-center justify-center border-2 transition-all duration-500 z-10 bg-[#0A0A0A]",
                isCompleted ? "bg-emerald-500 border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.4)]" :
                    isCurrent ? "border-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)] scale-110" : "border-stone-700"
            )}>
                {isCompleted && <Check className="w-3 h-3 text-black stroke-[3]" />}
                {isCurrent && <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />}
            </div>
            <div className={cn("transition-all duration-300", isCurrent ? "translate-x-1" : "")}>
                <span className={cn("text-sm font-medium block mb-0.5 transition-colors", isCompleted ? "text-stone-500" : isCurrent ? "text-white" : "text-stone-600")}>{step}</span>
                {isCurrent && (
                    <span className="text-emerald-400 text-xs font-mono flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
                        Running...
                    </span>
                )}
            </div>
        </div>
    );
};

const LogTerminal = ({ logs }: { logs: string[] }) => {
    const scrollRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [logs]);

    return (
        <div className="bg-[#1c1917] rounded-xl overflow-hidden font-mono text-xs h-[400px] flex flex-col shadow-2xl border border-stone-800">
            <div className="bg-[#292524] px-4 py-2 flex items-center gap-2 border-b border-white/5">
                <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]" />
                    <div className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]" />
                    <div className="w-2.5 h-2.5 rounded-full bg-[#27c93f]" />
                </div>
                <span className="ml-2 text-white/30 text-[10px] uppercase tracking-wider font-bold">DebugIt Agent v2.4.0 --verbose</span>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-2 p-4 custom-scrollbar">
                {logs.map((log, i) => (
                    <div key={i} className="flex gap-3 text-stone-300 border-l-2 border-transparent hover:border-white/10 hover:bg-white/[0.02] -mx-4 px-4 py-0.5 transition-colors">
                        <span className="text-stone-500 shrink-0 w-16 text-[10px] pt-0.5">{new Date().toLocaleTimeString([], { hour12: false })}</span>
                        <span className={cn(
                            "flex-1 break-all",
                            log.includes("ERROR") || log.includes("error") ? "text-red-400 font-bold" :
                                log.includes("SUCCESS") || log.includes("fixed") || log.includes("PASS") ? "text-emerald-400 font-bold" :
                                    log.includes("WARNING") || log.includes("FALLBACK") ? "text-amber-400" :
                                        "text-stone-300"
                        )}>
                            {log}
                        </span>
                    </div>
                ))}
                {logs.length === 0 && <span className="text-stone-500 italic">Waiting for input...</span>}
                <div className="animate-pulse text-emerald-500 pl-19">▊</div>
            </div>
        </div>
    );
};

/** Render a unified diff in the DebugIt reference style */
const InlineDiffView = ({ fix }: { fix: FixEntry }) => {
    if (!fix.diff || !fix.diff.trim()) return null;

    const lines = fix.diff.split('\n');
    const diffLines: { type: 'context' | 'remove' | 'add'; text: string }[] = [];

    for (const line of lines) {
        if (line.startsWith('---') || line.startsWith('+++') || line.startsWith('@@') || line.startsWith('diff ') || line.startsWith('index ')) continue;
        if (line.startsWith('-')) diffLines.push({ type: 'remove', text: line.slice(1) });
        else if (line.startsWith('+')) diffLines.push({ type: 'add', text: line.slice(1) });
        else if (line.startsWith(' ')) diffLines.push({ type: 'context', text: line.slice(1) });
        else if (line === '') diffLines.push({ type: 'context', text: '' });
    }

    return (
        <div className="bg-black/30 rounded-2xl border border-white/5 overflow-hidden font-mono text-sm leading-relaxed shadow-inner backdrop-blur-sm">
            <div className="flex items-center bg-white/5 border-b border-white/5 px-4 py-2.5 text-xs text-stone-400 font-bold select-none">
                <Command className="w-3 h-3 mr-2 text-emerald-500" /> Diff View — {fix.file}
                <div className="ml-auto flex gap-3">
                    <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-bold border", BUG_TYPE_BADGE[fix.bug_type] || "bg-white/5 text-stone-400 border-white/10")}>
                        {fix.bug_type}
                    </span>
                    <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-bold border",
                        fix.status === "fixed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"
                    )}>
                        {fix.status === "fixed" ? "FIXED" : "FAILED"}
                    </span>
                </div>
            </div>
            <div className="py-2">
                {diffLines.map((dl, i) => (
                    <div
                        key={i}
                        className={cn(
                            "px-6 py-1 w-full",
                            dl.type === 'remove' ? "bg-red-500/5 border-l-[3px] border-red-500/40 text-stone-500 opacity-60" :
                                dl.type === 'add' ? "bg-emerald-500/10 border-l-[3px] border-emerald-500 text-white font-medium" :
                                    "text-stone-500 pl-[calc(1.5rem+3px)]"
                        )}
                    >
                        {dl.type === 'remove' && <span className="select-none text-red-500/50 mr-4 font-bold">-</span>}
                        {dl.type === 'add' && <span className="select-none text-emerald-500 mr-4 font-bold">+</span>}
                        {dl.text || '\u00A0'}
                    </div>
                ))}
            </div>
        </div>
    );
};

// ── Main Dashboard ──

export const Dashboard = () => {
    const {
        user,
        repoUrl, teamName, leaderName,
        setRepoUrl, setTeamName, setLeaderName,
        runId, results, wsEvents, loading, error,
        startRun, setLoading, setError,
    } = useHealStore();

    const [activeTab, setActiveTab] = useState('analysis');

    // Pre-fill leader name from GitHub profile on first load
    useEffect(() => {
        if (user?.name && !leaderName) {
            setLeaderName(user.name);
        }
    }, [user, leaderName, setLeaderName]);

    // WebSocket connection
    useWebSocket(runId);

    // Interactive background
    const mouseX = useMotionValue(0);
    const mouseY = useMotionValue(0);
    useEffect(() => {
        const handleMouseMove = ({ clientX, clientY }: MouseEvent) => {
            mouseX.set(clientX);
            mouseY.set(clientY);
        };
        window.addEventListener("mousemove", handleMouseMove);
        return () => window.removeEventListener("mousemove", handleMouseMove);
    }, [mouseX, mouseY]);

    // Derive job status
    type JobStatus = 'IDLE' | 'RUNNING' | 'FIXED' | 'FAILED';
    let jobStatus: JobStatus = 'IDLE';
    if (runId && !results) jobStatus = 'RUNNING';
    if (results?.final_status === 'PASSED') jobStatus = 'FIXED';
    if (results?.final_status === 'FAILED') jobStatus = 'FAILED';
    if (error && !results) jobStatus = 'FAILED';

    // Derive current step from WS events
    const startedNodes = new Set<string>();
    const endedNodes = new Set<string>();
    for (const ev of wsEvents) {
        if (ev.event_type === 'node_start' && ev.node) startedNodes.add(ev.node);
        if (ev.event_type === 'node_end' && ev.node) endedNodes.add(ev.node);
    }
    let currentStep = 0;
    for (let i = 0; i < PIPELINE_NODES.length; i++) {
        if (endedNodes.has(PIPELINE_NODES[i])) currentStep = i + 1;
        else if (startedNodes.has(PIPELINE_NODES[i])) { currentStep = i; break; }
    }
    if (jobStatus === 'FIXED' || jobStatus === 'FAILED') currentStep = PIPELINE_STEPS.length;

    // Convert WS events to log lines
    const logs = wsEvents.map(ev => {
        const prefix = ev.node ? `[${ev.node}] ` : '';
        return `${prefix}${ev.message}`;
    });

    // Metrics
    const totalFailures = results?.total_failures_detected ?? 0;
    const fixedCount = results?.fixes?.filter(f => f.status === 'fixed').length ?? 0;
    const totalTime = results ? `${Math.round(results.total_time_seconds)}s` : '--';
    const score = results?.score?.total ?? 0;

    // Submit handler
    const handleSubmit = async () => {
        if (!repoUrl.includes('github.com/')) return;
        setLoading(true);
        setError(null);
        try {
            const resp = await startHeal(repoUrl.trim(), teamName.trim(), leaderName.trim());
            startRun(resp.run_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to start healing');
        }
    };

    // Fixes with diffs
    const fixesWithDiffs = results?.fixes?.filter(f => f.diff && f.diff.trim()) ?? [];

    return (
        <div className="min-h-screen bg-[#050505] text-stone-200 font-sans selection:bg-[#00ff9d]/30 selection:text-[#00ff9d] relative overflow-hidden">
            {/* Backgrounds */}
            <div className="fixed inset-0 z-0 pointer-events-none"><ParticleWave /></div>
            <div className="fixed inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay z-0"></div>
            <motion.div
                style={{ x: useTransform(mouseX, x => x / 20), y: useTransform(mouseY, y => y / 20) }}
                transition={{ type: "spring", damping: 50, stiffness: 100 }}
                className="fixed top-[-10%] right-[-10%] w-[600px] h-[600px] bg-[#00ff9d]/5 rounded-full blur-[150px] pointer-events-none z-0"
            />
            <motion.div
                style={{ x: useTransform(mouseX, x => x * -0.05), y: useTransform(mouseY, y => y * -0.05) }}
                transition={{ type: "spring", damping: 50, stiffness: 100 }}
                className="fixed bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-[#8b5cf6]/5 rounded-full blur-[150px] pointer-events-none z-0"
            />
            <div className="fixed inset-0 bg-[linear-gradient(to_right,#80808005_1px,transparent_1px),linear-gradient(to_bottom,#80808005_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)] z-0" />

            <Navbar />

            <main className="relative z-10 max-w-7xl mx-auto px-4 py-8 space-y-8">
                {/* Metrics Row */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <MetricsCard label="Failures Found" value={String(totalFailures)} icon={AlertOctagon} delay={0.1} />
                    <MetricsCard label="Fixes Applied" value={String(fixedCount)} trend={results ? `${fixedCount}/${results.fixes?.length ?? 0}` : undefined} icon={CheckCircle} delay={0.2} />
                    <MetricsCard label="Fix Time" value={totalTime} trend={results && results.total_time_seconds < 300 ? "+10 bonus" : undefined} icon={Clock} delay={0.3} />
                    <MetricsCard label="Score" value={String(score)} trend={score > 100 ? "Perfect!" : undefined} icon={Cpu} delay={0.4} />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Left Column */}
                    <div className="space-y-6">
                        {/* Input Card */}
                        <motion.div
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="bg-white/5 border border-white/10 rounded-3xl p-1 shadow-2xl relative overflow-hidden group ring-1 ring-white/5 backdrop-blur-xl"
                        >
                            <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />
                            <div className="bg-transparent rounded-[22px] p-6 relative z-10">
                                <h2 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                                    <div className="p-2 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20 shadow-sm backdrop-blur-md">
                                        <Terminal className="w-4 h-4" />
                                    </div>
                                    New Investigation
                                </h2>

                                <div className="space-y-4">
                                    <div>
                                        <label className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-1.5 block">Repository URL</label>
                                        <div className="flex items-center bg-black/20 border border-white/10 rounded-xl px-3 py-3 focus-within:border-emerald-500/50 focus-within:bg-black/40 transition-all shadow-inner backdrop-blur-sm">
                                            <GitBranch className="w-4 h-4 text-stone-500 mr-2" />
                                            <input
                                                type="text"
                                                placeholder="https://github.com/org/repo"
                                                value={repoUrl}
                                                onChange={(e) => setRepoUrl(e.target.value)}
                                                disabled={loading}
                                                className="bg-transparent border-none outline-none text-sm w-full text-stone-200 placeholder-stone-600 font-medium font-mono"
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-1.5 block">Team Name</label>
                                        <div className="flex items-center bg-black/20 border border-white/10 rounded-xl px-3 py-3 focus-within:border-emerald-500/50 focus-within:bg-black/40 transition-all shadow-inner backdrop-blur-sm">
                                            <Users className="w-4 h-4 text-stone-500 mr-2" />
                                            <input
                                                type="text"
                                                placeholder="RIFT ORGANISERS"
                                                value={teamName}
                                                onChange={(e) => setTeamName(e.target.value)}
                                                disabled={loading}
                                                className="bg-transparent border-none outline-none text-sm w-full text-stone-200 placeholder-stone-600 font-medium font-mono"
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label className="text-xs text-stone-400 font-bold uppercase tracking-wider mb-1.5 block">Team Leader</label>
                                        <div className="flex items-center bg-black/20 border border-white/10 rounded-xl px-3 py-3 focus-within:border-emerald-500/50 focus-within:bg-black/40 transition-all shadow-inner backdrop-blur-sm">
                                            <User className="w-4 h-4 text-stone-500 mr-2" />
                                            <input
                                                type="text"
                                                placeholder="Saiyam Kumar"
                                                value={leaderName}
                                                onChange={(e) => setLeaderName(e.target.value)}
                                                disabled={loading}
                                                className="bg-transparent border-none outline-none text-sm w-full text-stone-200 placeholder-stone-600 font-medium font-mono"
                                            />
                                        </div>
                                    </div>

                                    <button
                                        onClick={handleSubmit}
                                        disabled={jobStatus === 'RUNNING' || loading || !repoUrl.trim() || !teamName.trim() || !leaderName.trim()}
                                        className="w-full bg-white text-black font-bold py-4 rounded-xl hover:bg-emerald-400 hover:shadow-[0_0_20px_rgba(52,211,153,0.4)] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed group relative overflow-hidden active:scale-[0.98]"
                                    >
                                        {jobStatus === 'RUNNING' ? (
                                            <>
                                                <span className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin"></span>
                                                Analyzing...
                                            </>
                                        ) : (
                                            <>
                                                <Zap className="w-4 h-4 fill-black" />
                                                Start Fix Agent
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </motion.div>

                        {/* Stepper */}
                        <AnimatePresence>
                            {jobStatus !== 'IDLE' && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, height: 'auto', scale: 1 }}
                                    exit={{ opacity: 0, height: 0, scale: 0.95 }}
                                    className="bg-white/5 border border-white/10 rounded-3xl p-6 shadow-xl ring-1 ring-white/5 backdrop-blur-md"
                                >
                                    <div className="flex items-center justify-between mb-6 border-b border-white/10 pb-4">
                                        <h3 className="text-sm font-bold text-white flex items-center gap-2">
                                            <Activity className="w-4 h-4 text-emerald-400" />
                                            Live Progress
                                        </h3>
                                        <span className={cn(
                                            "text-[10px] font-bold px-2 py-0.5 rounded-full border",
                                            jobStatus === 'RUNNING' ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 animate-pulse" :
                                                jobStatus === 'FIXED' ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                                                    "bg-red-500/10 text-red-400 border-red-500/20"
                                        )}>
                                            {jobStatus === 'RUNNING' ? 'AGENT ACTIVE' : jobStatus === 'FIXED' ? 'COMPLETE' : 'FAILED'}
                                        </span>
                                    </div>
                                    <div className="relative z-10 pl-2">
                                        {PIPELINE_STEPS.map((step, i) => (
                                            <StepItem key={i} step={step} currentStep={currentStep} index={i} />
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Score Card (when results available) */}
                        {results && (
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="bg-white/5 border border-white/10 rounded-3xl p-6 shadow-xl ring-1 ring-white/5 backdrop-blur-md"
                            >
                                <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                                    <Zap className="w-4 h-4 text-emerald-400" />
                                    Score Breakdown
                                </h3>
                                <div className="text-center mb-4">
                                    <span className="text-5xl font-display font-bold text-emerald-400">{results.score.total}</span>
                                    <span className="text-lg text-stone-500 ml-1">/ 110</span>
                                </div>
                                <div className="w-full bg-white/5 rounded-full h-2 mb-4">
                                    <div className="bg-emerald-500 h-2 rounded-full transition-all duration-700" style={{ width: `${Math.min(100, Math.round((results.score.total / 110) * 100))}%` }} />
                                </div>
                                <div className="space-y-2 text-sm">
                                    <div className="flex justify-between"><span className="text-stone-400">Base</span><span className="text-stone-200 font-bold">{results.score.base}</span></div>
                                    <div className="flex justify-between"><span className="text-stone-400">Speed bonus</span><span className={results.score.speed_bonus > 0 ? "text-emerald-400 font-bold" : "text-stone-500"}>+{results.score.speed_bonus}</span></div>
                                    <div className="flex justify-between"><span className="text-stone-400">Penalty</span><span className={results.score.efficiency_penalty > 0 ? "text-red-400 font-bold" : "text-stone-500"}>-{results.score.efficiency_penalty}</span></div>
                                </div>
                            </motion.div>
                        )}
                    </div>

                    {/* Right Column */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Success Banner */}
                        {jobStatus === 'FIXED' && (
                            <motion.div
                                initial={{ opacity: 0, y: -20 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="bg-emerald-900/10 border border-emerald-500/30 rounded-3xl p-5 flex items-center justify-between shadow-[0_0_40px_-10px_rgba(16,185,129,0.1)] relative overflow-hidden backdrop-blur-md"
                            >
                                <div className="absolute inset-0 bg-emerald-500/5 pointer-events-none" />
                                <div className="flex items-center gap-5 relative z-10">
                                    <div className="bg-emerald-500 p-3 rounded-2xl shadow-lg shadow-emerald-500/20">
                                        <CheckCircle className="w-6 h-6 text-black" />
                                    </div>
                                    <div>
                                        <h3 className="text-white font-bold text-xl mb-0.5">Auto-Fix Successful</h3>
                                        <p className="text-emerald-400/80 text-sm font-medium">All tests passing. {results?.total_commits ?? 0} commit(s) pushed.</p>
                                    </div>
                                </div>
                                {results?.branch_name && (
                                    <div className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10 text-xs font-bold text-stone-400 relative z-10">
                                        <GitBranch className="w-3.5 h-3.5" />
                                        {results.branch_name}
                                    </div>
                                )}
                            </motion.div>
                        )}

                        {/* Failed Banner */}
                        {jobStatus === 'FAILED' && (
                            <motion.div
                                initial={{ opacity: 0, y: -20 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="bg-red-900/10 border border-red-500/30 rounded-3xl p-5 flex items-center gap-5 relative overflow-hidden backdrop-blur-md"
                            >
                                <div className="bg-red-500 p-3 rounded-2xl shadow-lg shadow-red-500/20">
                                    <AlertOctagon className="w-6 h-6 text-black" />
                                </div>
                                <div>
                                    <h3 className="text-white font-bold text-xl mb-0.5">Fix Incomplete</h3>
                                    <p className="text-red-400/80 text-sm font-medium">{error || `${fixedCount} of ${results?.fixes?.length ?? 0} fixes applied successfully.`}</p>
                                </div>
                            </motion.div>
                        )}

                        {/* Tabbed View */}
                        <div className="bg-white/5 border border-white/10 rounded-3xl shadow-2xl shadow-black/50 overflow-hidden min-h-[500px] flex flex-col relative ring-1 ring-white/5 backdrop-blur-xl">
                            <div className="flex border-b border-white/10 bg-black/20 p-2 gap-2 backdrop-blur-md">
                                {[
                                    { id: 'analysis', icon: AlertOctagon, label: 'Analysis' },
                                    { id: 'fix', icon: FileCode, label: 'Code Fix' },
                                    { id: 'logs', icon: Terminal, label: 'Agent Logs' },
                                ].map(tab => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={cn(
                                            "flex-1 py-3 text-sm font-bold rounded-xl flex items-center justify-center gap-2 transition-all relative group",
                                            activeTab === tab.id ? "bg-white/10 text-white shadow-inner border border-white/10 backdrop-blur-sm" : "text-stone-500 hover:text-stone-300 hover:bg-white/5"
                                        )}
                                    >
                                        <tab.icon className={cn("w-4 h-4", activeTab === tab.id ? "text-emerald-400" : "text-stone-500")} />
                                        {tab.label}
                                    </button>
                                ))}
                            </div>

                            <div className="p-6 flex-1 bg-transparent">
                                {/* Agent Logs Tab */}
                                {activeTab === 'logs' && <LogTerminal logs={logs} />}

                                {/* Analysis Tab */}
                                {activeTab === 'analysis' && (
                                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                                        {!results && jobStatus === 'IDLE' && (
                                            <div className="text-center py-20 text-stone-500">
                                                <AlertOctagon className="w-12 h-12 mx-auto mb-4 opacity-30" />
                                                <p className="text-sm font-medium">No analysis yet. Start an investigation above.</p>
                                            </div>
                                        )}
                                        {!results && jobStatus === 'RUNNING' && (
                                            <div className="text-center py-20 text-stone-500">
                                                <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-4"></div>
                                                <p className="text-sm font-medium">Analysis in progress...</p>
                                            </div>
                                        )}
                                        {results && (
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                {/* Failure Card */}
                                                <div className="bg-red-500/5 border border-red-500/10 rounded-3xl p-6 relative overflow-hidden backdrop-blur-sm">
                                                    <div className="absolute top-0 right-0 w-32 h-32 bg-red-500/5 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2" />
                                                    <div className="flex items-center gap-2 mb-3 relative z-10">
                                                        <div className="bg-red-500/10 p-1.5 rounded-lg border border-red-500/20 shadow-sm">
                                                            <AlertOctagon className="w-4 h-4 text-red-400" />
                                                        </div>
                                                        <h4 className="text-red-400 font-bold text-sm">Failures Detected ({totalFailures})</h4>
                                                    </div>
                                                    <div className="space-y-3 relative z-10">
                                                        {results.fixes.slice(0, 5).map((fix, i) => (
                                                            <div key={i} className="bg-black/40 p-3 rounded-xl font-mono text-xs text-stone-300 border border-white/5 shadow-inner">
                                                                <span className={cn("font-bold mr-2", fix.status === 'fixed' ? "text-emerald-400" : "text-red-400")}>
                                                                    {fix.status === 'fixed' ? 'FIXED' : 'FAILED'}
                                                                </span>
                                                                <span className="text-stone-400">{fix.issue_line}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                {/* Summary Card */}
                                                <div className="bg-white/5 border border-white/5 rounded-3xl p-6 hover:border-emerald-500/20 transition-all backdrop-blur-sm">
                                                    <div className="flex items-center gap-2 mb-4">
                                                        <div className="bg-emerald-500/10 p-1.5 rounded-lg border border-emerald-500/20">
                                                            <Shield className="w-4 h-4 text-emerald-400" />
                                                        </div>
                                                        <h4 className="text-white font-bold text-sm">Run Summary</h4>
                                                    </div>
                                                    <ul className="space-y-4">
                                                        <li className="flex gap-3">
                                                            <div className="w-2 h-2 rounded-full bg-emerald-500 mt-2 shrink-0 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                                                            <span className="text-sm text-stone-400 leading-relaxed font-medium">
                                                                Repository: <code className="bg-emerald-500/10 text-emerald-400 px-1 rounded border border-emerald-500/20">{results.repo_url.replace('https://github.com/', '')}</code>
                                                            </span>
                                                        </li>
                                                        <li className="flex gap-3">
                                                            <div className="w-2 h-2 rounded-full bg-emerald-500 mt-2 shrink-0 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                                                            <span className="text-sm text-stone-400 leading-relaxed font-medium">
                                                                Branch: <code className="bg-emerald-500/10 text-emerald-400 px-1 rounded border border-emerald-500/20">{results.branch_name}</code>
                                                            </span>
                                                        </li>
                                                        <li className="flex gap-3">
                                                            <div className="w-2 h-2 rounded-full bg-emerald-500 mt-2 shrink-0 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                                                            <span className="text-sm text-stone-400 leading-relaxed font-medium">
                                                                {results.total_commits} commit(s) in {Math.round(results.total_time_seconds)}s — {fixedCount}/{results.fixes.length} fixes applied
                                                            </span>
                                                        </li>
                                                        {results.ci_runs.length > 0 && (
                                                            <li className="flex gap-3">
                                                                <div className="w-2 h-2 rounded-full bg-emerald-500 mt-2 shrink-0 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                                                                <span className="text-sm text-stone-400 leading-relaxed font-medium">
                                                                    CI: {results.ci_runs[results.ci_runs.length - 1].status} ({results.ci_runs[results.ci_runs.length - 1].mode})
                                                                </span>
                                                            </li>
                                                        )}
                                                    </ul>
                                                </div>
                                            </div>
                                        )}
                                    </motion.div>
                                )}

                                {/* Code Fix Tab */}
                                {activeTab === 'fix' && (
                                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                                        {fixesWithDiffs.length === 0 && (
                                            <div className="text-center py-20 text-stone-500">
                                                <FileCode className="w-12 h-12 mx-auto mb-4 opacity-30" />
                                                <p className="text-sm font-medium">{results ? 'No diffs generated for this run.' : 'No fixes yet. Start an investigation.'}</p>
                                            </div>
                                        )}
                                        {fixesWithDiffs.map((fix, i) => (
                                            <div key={i} className="space-y-4">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-sm text-stone-500 font-medium flex items-center gap-2">
                                                        <FileCode className="w-4 h-4 text-stone-400" />
                                                        {fix.file}
                                                    </span>
                                                    <span className={cn("text-xs px-3 py-1 rounded-full border font-bold", BUG_TYPE_BADGE[fix.bug_type] || "bg-white/5 text-stone-400 border-white/10")}>
                                                        {fix.bug_type}
                                                    </span>
                                                </div>
                                                <InlineDiffView fix={fix} />
                                                <div className="p-4 rounded-2xl border border-white/5 bg-white/5 shadow-sm flex items-center justify-between backdrop-blur-sm">
                                                    <div>
                                                        <h4 className="text-sm font-bold text-white mb-1">Commit</h4>
                                                        <p className="text-xs text-stone-500 font-mono">{fix.commit_message}</p>
                                                    </div>
                                                    <div className="flex gap-4 text-xs font-bold text-stone-500">
                                                        <div className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
                                                            <GitBranch className="w-3.5 h-3.5" />
                                                            iter #{fix.iteration}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </motion.div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};
