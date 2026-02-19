export const Footer = () => (
    <div className="w-full border-t border-[#00ff9d] pt-8 mt-16 text-center text-slate-500 text-[10px] font-mono uppercase tracking-wider flex gap-8 justify-center pb-8">
        <a href="#" className="hover:text-[#00ff9d] transition-colors relative group">
            Privacy Protocol
            <span className="absolute -bottom-1 left-0 w-0 h-[1px] bg-[#00ff9d] group-hover:w-full transition-all duration-300"></span>
        </a>
        <a href="#" className="hover:text-[#00ff9d] transition-colors relative group">
            Terms of Engagement
            <span className="absolute -bottom-1 left-0 w-0 h-[1px] bg-[#00ff9d] group-hover:w-full transition-all duration-300"></span>
        </a>
        <a href="#" className="hover:text-[#00ff9d] transition-colors relative group">
            GitHub Neural Link
            <span className="absolute -bottom-1 left-0 w-0 h-[1px] bg-[#00ff9d] group-hover:w-full transition-all duration-300"></span>
        </a>
    </div>
);
