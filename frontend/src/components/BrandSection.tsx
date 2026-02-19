import { motion } from 'framer-motion';

export const BrandSection = () => (
    <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="flex flex-col items-center space-y-6 mb-10"
    >
        <div className="text-center">
            <h1 className="text-4xl md:text-5xl font-bold tracking-tighter text-white mb-3 font-display relative inline-block group cursor-default">
                <span className="relative z-10 group-hover:text-[#00ff9d] transition-colors duration-300">Debug</span>
                <span className="text-[#8b5cf6]">It</span>
                <span className="absolute top-0 left-0 -ml-1 opacity-0 group-hover:opacity-70 group-hover:animate-glitch text-[#00ff9d] z-0">DebugIt</span>
                <span className="absolute top-0 left-0 ml-1 opacity-0 group-hover:opacity-70 group-hover:animate-glitch text-[#8b5cf6] animation-delay-200 z-0">DebugIt</span>
            </h1>

            <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="text-slate-400 text-sm md:text-base font-mono mt-4 flex items-center justify-center gap-2"
            >
                <span className="w-2 h-2 rounded-full bg-[#00ff9d] animate-pulse"></span>
                SYSTEM STATUS: <span className="text-[#00ff9d]">ONLINE</span>
            </motion.p>
            <p className="text-slate-500 text-xs mt-2 uppercase tracking-[0.2em] font-light">
                Self-Healing Debugging Powered by AI
            </p>
        </div>
    </motion.div>
);
