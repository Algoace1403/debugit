import { motion } from 'framer-motion';

const testimonials = [
    { name: "Aarav Sharma", compliment: "DebugIt makes tracking GitHub issues insanely fast — it saved me hours this week!", avatar_url: "https://i.pravatar.cc/150?img=1" },
    { name: "Krishna Bhatia", compliment: "The UI is super clean — debugging repos feels effortless with DebugIt.", avatar_url: "https://i.pravatar.cc/150?img=2" },
    { name: "Riya Patel", compliment: "I love how DebugIt integrates directly with GitHub workflows!", avatar_url: "https://i.pravatar.cc/150?img=3" },
    { name: "Arjun Mehta", compliment: "The automated error insights are a game changer.", avatar_url: "https://i.pravatar.cc/150?img=4" },
    { name: "Sneha Kapoor", compliment: "DebugIt helped our team resolve PR issues 2x faster.", avatar_url: "https://i.pravatar.cc/150?img=5" },
    { name: "Rahul Verma", compliment: "The GitHub login and repo sync is seamless — brilliant work!", avatar_url: "https://i.pravatar.cc/150?img=6" },
    { name: "Ishita Roy", compliment: "I've never seen debugging analytics presented this clearly.", avatar_url: "https://i.pravatar.cc/150?img=7" },
    { name: "Karan Malhotra", compliment: "DebugIt feels like having a senior dev reviewing my code.", avatar_url: "https://i.pravatar.cc/150?img=8" },
    { name: "Neha Singh", compliment: "The dashboard insights are powerful yet easy to understand.", avatar_url: "https://i.pravatar.cc/150?img=9" },
    { name: "Aditya Nair", compliment: "Repo error tracking has never been this organized.", avatar_url: "https://i.pravatar.cc/150?img=10" },
    { name: "Pooja Desai", compliment: "I love the interactive debugging timeline feature.", avatar_url: "https://i.pravatar.cc/150?img=11" },
    { name: "Vikram Joshi", compliment: "DebugIt integrates perfectly into my CI/CD pipeline.", avatar_url: "https://i.pravatar.cc/150?img=12" },
    { name: "Ananya Iyer", compliment: "The performance insights helped optimize our codebase.", avatar_url: "https://i.pravatar.cc/150?img=13" },
    { name: "Rohit Gupta", compliment: "Bug detection is fast, accurate, and developer-friendly.", avatar_url: "https://i.pravatar.cc/150?img=14" },
    { name: "Meera Chawla", compliment: "DebugIt makes collaboration on GitHub debugging so smooth.", avatar_url: "https://i.pravatar.cc/150?img=15" },
    { name: "Siddharth Jain", compliment: "The AI suggestions for fixes are incredibly helpful.", avatar_url: "https://i.pravatar.cc/150?img=16" },
    { name: "Tanya Arora", compliment: "I reduced production bugs thanks to DebugIt alerts.", avatar_url: "https://i.pravatar.cc/150?img=17" },
    { name: "Dev Khanna", compliment: "The GitHub repo visualization tools are next level.", avatar_url: "https://i.pravatar.cc/150?img=18" },
    { name: "Nikhil Bansal", compliment: "DebugIt turned complex debugging into a simple workflow.", avatar_url: "https://i.pravatar.cc/150?img=19" },
    { name: "Simran Kaur", compliment: "Absolutely love the real-time error monitoring!", avatar_url: "https://i.pravatar.cc/150?img=20" },
];

const TestimonialCard = ({ data }: { data: typeof testimonials[0] }) => {
    const handle = `@${data.name.toLowerCase().replace(/\s+/g, '_')}`;
    const daysAgo = data.name.length % 5;
    const date = `${daysAgo === 0 ? 'Today' : `${daysAgo}d ago`} · 2:30 PM`;

    return (
        <div className="min-w-[320px] max-w-sm w-full bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 shadow-lg hover:shadow-[#00ff9d]/20 hover:border-[#00ff9d]/30 transition-all duration-300 mx-4">
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                    <div className="flex-shrink-0">
                        <img src={data.avatar_url} alt={data.name} className="w-10 h-10 rounded-full object-cover border border-white/10" />
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center space-x-1">
                            <span className="font-bold text-white hover:underline truncate font-display">{data.name}</span>
                        </div>
                        <span className="text-slate-400 text-xs hover:underline font-mono">{handle}</span>
                    </div>
                </div>
                <div className="flex-shrink-0 text-[#00ff9d]">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                    </svg>
                </div>
            </div>
            <div className="mb-3">
                <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap font-sans">{data.compliment}</p>
            </div>
            <div className="text-slate-500 text-[10px] font-mono">{date}</div>
        </div>
    );
};

export const Testimonials = () => {
    const firstRowData = [...testimonials.slice(0, 10), ...testimonials.slice(0, 10)];
    const secondRowData = [...testimonials.slice(10), ...testimonials.slice(10)];

    return (
        <div className="w-full overflow-hidden py-12 relative flex flex-col gap-8">
            <div className="absolute inset-y-0 left-0 w-20 bg-gradient-to-r from-[#050505] to-transparent z-10 pointer-events-none" />
            <div className="absolute inset-y-0 right-0 w-20 bg-gradient-to-l from-[#050505] to-transparent z-10 pointer-events-none" />

            <motion.div
                className="flex items-center"
                animate={{ x: ["0%", "-50%"] }}
                transition={{ duration: 40, ease: "linear", repeat: Infinity }}
                style={{ width: "max-content" }}
            >
                {firstRowData.map((testimonial, index) => (
                    <TestimonialCard key={`row1-${testimonial.name}-${index}`} data={testimonial} />
                ))}
            </motion.div>

            <motion.div
                className="flex items-center"
                animate={{ x: ["-50%", "0%"] }}
                transition={{ duration: 40, ease: "linear", repeat: Infinity }}
                style={{ width: "max-content" }}
            >
                {secondRowData.map((testimonial, index) => (
                    <TestimonialCard key={`row2-${testimonial.name}-${index}`} data={testimonial} />
                ))}
            </motion.div>
        </div>
    );
};
