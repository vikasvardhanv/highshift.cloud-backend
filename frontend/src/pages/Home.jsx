import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle, Code, Terminal } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Home() {
    return (
        <div className="flex flex-col items-center justify-center pt-20 pb-20">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="text-center max-w-4xl"
            >
                <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold uppercase tracking-wider border border-primary/20 mb-6 inline-block">
                    Social Media Automation
                </span>
                <h1 className="text-5xl md:text-7xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-gray-500 mb-6 leading-tight">
                    One API to <br /> <span className="text-primary">Rule Them All</span>
                </h1>
                <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
                    Upload your content to TikTok, Instagram, YouTube, and 7 more platforms with a single API request.
                    Automate your social media presence today.
                </p>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                    <Link to="/dashboard" className="px-8 py-4 rounded-full bg-primary hover:bg-primaryHover text-white font-semibold text-lg transition-all shadow-[0_0_40px_rgba(99,102,241,0.4)] flex items-center gap-2">
                        Start Building <ArrowRight className="w-5 h-5" />
                    </Link>
                    <a href="#" className="px-8 py-4 rounded-full bg-white/5 hover:bg-white/10 text-white font-semibold text-lg transition-all border border-white/10 flex items-center gap-2">
                        View Documentation
                    </a>
                </div>
            </motion.div>

            {/* Code Snippet */}
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2, duration: 0.5 }}
                className="mt-20 w-full max-w-3xl glass-card rounded-xl overflow-hidden shadow-2xl"
            >
                <div className="flex items-center gap-2 px-4 py-3 bg-black/40 border-b border-white/5">
                    <div className="w-3 h-3 rounded-full bg-red-500" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500" />
                    <div className="w-3 h-3 rounded-full bg-green-500" />
                    <span className="ml-2 text-xs text-gray-500">upload.js</span>
                </div>
                <div className="p-6 bg-[#0d0d0d] font-mono text-sm overflow-x-auto">
                    <pre className="text-gray-300">
                        <span className="text-purple-400">const</span> response = <span className="text-purple-400">await</span> axios.<span className="text-blue-400">post</span>(
                        <span className="text-green-400">'https://api.socialapi.com/post/multi'</span>,
                        {'{'}
                        <span className="text-orange-300">accounts</span>: [<span className="text-green-400">'twitter'</span>, <span className="text-green-400">'instagram'</span>, <span className="text-green-400">'youtube'</span>],
                        <span className="text-orange-300">content</span>: <span className="text-green-400">"Check out our new feature! 🚀"</span>
                        {'}'},
                        {'{'}
                        <span className="text-orange-300">headers</span>: {'{'} <span className="text-green-400">'X-API-Key'</span>: <span className="text-green-400">'YOUR_KEY_HERE'</span> {'}'}
                        {'}'}
                        );
                    </pre>
                </div>
            </motion.div>

            {/* Features Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-32 max-w-6xl w-full">
                <FeatureCard
                    icon={<CheckCircle className="text-green-400 w-6 h-6" />}
                    title="Multi-Platform"
                    desc="Support for Twitter, Instagram, YouTube, LinkedIn, and more."
                />
                <FeatureCard
                    icon={<Code className="text-blue-400 w-6 h-6" />}
                    title="Developer First"
                    desc="Designed for developers with clean REST API and clear documentation."
                />
                <FeatureCard
                    icon={<Terminal className="text-purple-400 w-6 h-6" />}
                    title="Secure OAuth"
                    desc="We handle the complex OAuth flows so you don't have to."
                />
            </div>
        </div>
    );
}

function FeatureCard({ icon, title, desc }) {
    return (
        <div className="glass-card p-6 rounded-xl hover:bg-white/5 transition-all">
            <div className="w-12 h-12 rounded-lg bg-white/5 flex items-center justify-center mb-4">
                {icon}
            </div>
            <h3 className="text-xl font-bold mb-2">{title}</h3>
            <p className="text-gray-400">{desc}</p>
        </div>
    );
}
