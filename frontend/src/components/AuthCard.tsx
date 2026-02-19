import { Github, Lock } from 'lucide-react';
import { motion } from 'framer-motion';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const AuthCard = () => {
    const handleGitHubLogin = () => {
        window.location.href = `${API_URL}/api/v1/auth/github`;
    };

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="w-full max-w-md relative group"
        >
            <div className="absolute -inset-1 bg-gradient-to-r from-[#00ff9d] via-[#8b5cf6] to-[#00ff9d] rounded-2xl opacity-70 blur-xl group-hover:opacity-100 transition duration-1000 group-hover:duration-200 animate-tilt"></div>

            <div className="relative w-full bg-[#0a0a0a] border border-[#ffffff10] rounded-2xl p-8 shadow-2xl overflow-hidden backdrop-blur-xl">
                <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_0%,rgba(0,255,157,0.03)_50%,transparent_100%)] bg-[length:100%_4px] pointer-events-none animate-scanline"></div>

                <div className="relative z-10 flex flex-col space-y-8">
                    <div className="space-y-2 text-center">
                        <h2 className="text-xl text-white font-display font-bold">Authenticate Access</h2>
                        <p className="text-xs text-slate-500 font-mono uppercase tracking-widest">Secure Gateway v2.4.0</p>
                    </div>

                    <motion.button
                        onClick={handleGitHubLogin}
                        whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(0, 255, 157, 0.4)" }}
                        whileTap={{ scale: 0.98 }}
                        className="relative flex items-center justify-center w-full gap-4 bg-white text-black hover:bg-[#00ff9d] hover:text-black font-bold py-4 px-6 rounded-xl transition-all duration-300 group/btn overflow-hidden cursor-pointer"
                    >
                        <Github className="w-6 h-6 transition-colors duration-300 group-hover/btn:text-black" />
                        <span className="font-display tracking-wide uppercase">Initialize GitHub Session</span>
                        <div className="absolute inset-0 bg-white/20 translate-y-full group-hover/btn:translate-y-0 transition-transform duration-300"></div>
                    </motion.button>

                    <div className="flex items-start gap-3 p-4 bg-[#00ff9d]/5 border border-[#00ff9d]/10 rounded-lg">
                        <Lock className="w-4 h-4 text-[#00ff9d] mt-0.5 shrink-0" />
                        <p className="text-[10px] text-slate-400 leading-relaxed font-mono">
                            <span className="text-[#00ff9d] font-bold">Heads up:</span> We request minimal permissions to scan repositories. Write access is strictly opt-in per incident.
                        </p>
                    </div>
                </div>
            </div>
        </motion.div>
    );
};
