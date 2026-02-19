import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { BrandSection } from '../components/BrandSection';
import { AuthCard } from '../components/AuthCard';
import { Features } from '../components/Features';
import { Footer } from '../components/Footer';
import { ParticleWave } from '../components/ParticleWave';
import { Testimonials } from '../components/Testimonials';

export const LoginPage = () => {
    const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

    useEffect(() => {
        const handleMouseMove = (event: MouseEvent) => {
            setMousePosition({ x: event.clientX, y: event.clientY });
        };
        window.addEventListener('mousemove', handleMouseMove);
        return () => window.removeEventListener('mousemove', handleMouseMove);
    }, []);

    return (
        <div className="min-h-screen w-full bg-[#050505] text-white flex flex-col items-center relative overflow-x-hidden overflow-y-auto font-sans selection:bg-[#00ff9d]/30 selection:text-[#00ff9d]">
            <div className="fixed inset-0 z-0 pointer-events-none">
                <ParticleWave />
            </div>

            <div className="fixed inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay z-0"></div>

            <motion.div
                animate={{ x: mousePosition.x / 20, y: mousePosition.y / 20 }}
                transition={{ type: "spring", damping: 50, stiffness: 100 }}
                className="fixed top-[-10%] right-[-10%] w-[600px] h-[600px] bg-[#00ff9d]/5 rounded-full blur-[150px] pointer-events-none z-0"
            />
            <motion.div
                animate={{ x: mousePosition.x * -0.05, y: mousePosition.y * -0.05 }}
                transition={{ type: "spring", damping: 50, stiffness: 100 }}
                className="fixed bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-[#8b5cf6]/5 rounded-full blur-[150px] pointer-events-none z-0"
            />

            <div className="fixed inset-0 bg-[linear-gradient(to_right,#80808005_1px,transparent_1px),linear-gradient(to_bottom,#80808005_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)] z-0" />

            <main className="relative z-10 flex flex-col items-center w-full px-4 max-w-5xl mx-auto py-20 min-h-screen justify-center">
                <BrandSection />
                <AuthCard />
                <Features />
            </main>

            <section className="relative z-10 w-full pb-20">
                <h3 className="text-center text-4xl font-display font-bold mb-10 text-white">
                    Developers <span className="text-[#00ff9d]">Love</span> DebugIt
                </h3>
                <Testimonials />
            </section>

            <div className="relative z-10 w-full">
                <Footer />
            </div>
        </div>
    );
};
