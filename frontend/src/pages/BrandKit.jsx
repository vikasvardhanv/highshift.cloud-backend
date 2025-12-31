import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { getBrandKit, updateBrandKit } from '../services/api';
import { Palette, Save, Briefcase, Globe, Hash, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

export default function BrandKit() {
    const [brand, setBrand] = useState({
        name: '',
        website: '',
        voiceDescription: '',
        colors: []
    });
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [colorInput, setColorInput] = useState('#000000');
    const apiKey = localStorage.getItem('social_api_key');

    useEffect(() => {
        if (apiKey) loadBrand();
    }, [apiKey]);

    if (!apiKey) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 animate-fade-in">
                <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6 border border-primary/20">
                    <Palette className="w-10 h-10 text-primary" />
                </div>
                <h2 className="text-3xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Unlock Brand Kit</h2>
                <p className="text-gray-400 mb-8 max-w-md mx-auto">Define your brand voice and colors so our AI can generate perfectly tailored content for you.</p>
                <Link to="/dashboard" className="px-8 py-3 rounded-full bg-primary hover:bg-primaryHover text-white font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105">
                    Connect Accounts
                </Link>
            </div>
        );
    }

    const loadBrand = async () => {
        setLoading(true);
        try {
            const data = await getBrandKit();
            setBrand({
                name: data.name || '',
                website: data.website || '',
                voiceDescription: data.voiceDescription || '',
                colors: data.colors || []
            });
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await updateBrandKit(brand);
            alert('Brand Kit saved!');
        } catch (err) {
            alert('Failed to save');
        } finally {
            setSaving(false);
        }
    };

    const addColor = () => {
        if (!brand.colors.includes(colorInput)) {
            setBrand({ ...brand, colors: [...brand.colors, colorInput] });
        }
    };

    const removeColor = (color) => {
        setBrand({ ...brand, colors: brand.colors.filter(c => c !== color) });
    };

    if (loading) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-primary" /></div>;

    return (
        <div className="max-w-4xl mx-auto pb-20">
            <div className="text-center mb-10">
                <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Brand Kit</h1>
                <p className="text-gray-400 mt-2">Define your identity. The AI Ghostwriter will use this to match your voice.</p>
            </div>

            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-card p-8 rounded-2xl">
                <form onSubmit={handleSave} className="space-y-8">
                    {/* Identity Section */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider flex items-center gap-2">
                                <Briefcase className="w-4 h-4" /> Brand Name
                            </label>
                            <input
                                type="text"
                                value={brand.name}
                                onChange={e => setBrand({ ...brand, name: e.target.value })}
                                className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:border-primary/50 outline-none"
                                placeholder="Acme Corp"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider flex items-center gap-2">
                                <Globe className="w-4 h-4" /> Website
                            </label>
                            <input
                                type="url"
                                value={brand.website}
                                onChange={e => setBrand({ ...brand, website: e.target.value })}
                                className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:border-primary/50 outline-none"
                                placeholder="https://acme.com"
                            />
                        </div>
                    </div>

                    {/* Voice Section */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider flex items-center gap-2">
                            <Hash className="w-4 h-4" /> Brand Voice & Tone
                        </label>
                        <p className="text-xs text-gray-500 mb-3">Describe how your brand speaks (e.g., "Professional yet witty," "Empathetic and calm," "Excited and emoji-heavy").</p>
                        <textarea
                            value={brand.voiceDescription}
                            onChange={e => setBrand({ ...brand, voiceDescription: e.target.value })}
                            className="w-full h-32 bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white focus:border-primary/50 outline-none resize-none"
                            placeholder="We speak like a helpful friend. We use simple language, avoid jargon, and occasionally use rocket emojis."
                        />
                    </div>

                    {/* Colors Section */}
                    <div>
                        <label className="block text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider flex items-center gap-2">
                            <Palette className="w-4 h-4" /> Brand Colors
                        </label>
                        <div className="flex items-center gap-4 mb-4">
                            <input
                                type="color"
                                value={colorInput}
                                onChange={e => setColorInput(e.target.value)}
                                className="h-10 w-20 rounded cursor-pointer bg-transparent"
                            />
                            <button
                                type="button"
                                onClick={addColor}
                                className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-bold uppercase transition-colors"
                            >
                                Add Color
                            </button>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            {brand.colors.map(color => (
                                <div key={color} className="group relative">
                                    <div
                                        className="w-12 h-12 rounded-full border border-white/10 shadow-lg"
                                        style={{ backgroundColor: color }}
                                    ></div>
                                    <button
                                        type="button"
                                        onClick={() => removeColor(color)}
                                        className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <strong className="text-xs px-1">×</strong>
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="pt-6 border-t border-white/5 flex justify-end">
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-8 py-3 rounded-full bg-primary hover:bg-primaryHover text-white font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105 flex items-center gap-2 disabled:opacity-50"
                        >
                            {saving ? <Loader2 className="animate-spin w-4 h-4" /> : <Save className="w-4 h-4" />}
                            Save Brand Kit
                        </button>
                    </div>
                </form>
            </motion.div>
        </div>
    );
}
