import { Shield, Zap, Activity, Bug } from 'lucide-react';
import { motion } from 'framer-motion';

const FeatureItem = ({ icon: Icon, text, delay }: { icon: React.ComponentType<{ className?: string }>; text: string; delay: number }) => (
    <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay, duration: 0.5 }}
        whileHover={{ x: 5, backgroundColor: "rgba(0, 255, 157, 0.1)", borderColor: "rgba(0, 255, 157, 0.3)" }}
        className="flex items-center gap-3 text-slate-400 text-xs px-4 py-2 rounded-lg bg-[#ffffff05] border border-[#ffffff0a] transition-colors duration-200 cursor-default"
    >
        <Icon className="w-4 h-4 text-[#00ff9d]" />
        <span className="font-mono tracking-tight uppercase">{text}</span>
    </motion.div>
);

export const Features = () => (
    <div className="flex flex-wrap justify-center gap-4 mt-12 max-w-2xl mx-auto">
        <FeatureItem icon={Activity} text="Real-time Failure Detection" delay={0.6} />
        <FeatureItem icon={Bug} text="AI Root Cause Analysis" delay={0.7} />
        <FeatureItem icon={Zap} text="Autonomous Patching" delay={0.8} />
        <FeatureItem icon={Shield} text="Zero-Trust Security" delay={0.9} />
    </div>
);
