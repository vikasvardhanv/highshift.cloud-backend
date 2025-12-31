import { Upload, Image as ImageIcon, Trash2, Plus } from 'lucide-react';
import { motion } from 'framer-motion';

export default function MediaLibrary() {
    // Mock Data
    const mediaItems = [
        { id: 1, url: 'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=400&h=400&fit=crop', name: 'Social_Strategy.jpg', size: '1.2 MB' },
        { id: 2, url: 'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=400&h=400&fit=crop', name: 'Product_Launch_Banner.png', size: '2.4 MB' },
        { id: 3, url: 'https://images.unsplash.com/photo-1522075469751-3a3a1ad19e2f?w=400&h=400&fit=crop', name: 'Team_Photo.jpg', size: '3.1 MB' },
    ];

    return (
        <div className="max-w-6xl mx-auto pb-20">
            <div className="flex items-center justify-between mb-10">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">Media Library</h1>
                    <p className="text-gray-400 mt-2">Manage your assets for posts and campaigns.</p>
                </div>
                <button className="px-6 py-3 rounded-full bg-white/10 hover:bg-white/20 border border-white/10 transition-all font-semibold flex items-center gap-2">
                    <Upload className="w-4 h-4" />
                    Upload Asset
                </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
                {/* Upload Placeholder */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                    className="aspect-square border-2 border-dashed border-white/20 rounded-2xl flex flex-col items-center justify-center text-gray-500 hover:text-white hover:border-primary/50 hover:bg-white/5 transition-all cursor-pointer group"
                >
                    <Plus className="w-8 h-8 mb-2 group-hover:scale-110 transition-transform" />
                    <span className="text-sm font-medium">Add New</span>
                </motion.div>

                {/* Media Items */}
                {mediaItems.map((item, i) => (
                    <motion.div
                        key={item.id}
                        initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.1 }}
                        className="group relative aspect-square rounded-2xl overflow-hidden glass-card"
                    >
                        <img src={item.url} alt={item.name} className="w-full h-full object-cover transition-transform group-hover:scale-105" />
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-4">
                            <p className="text-sm font-semibold truncate text-white">{item.name}</p>
                            <p className="text-xs text-gray-400">{item.size}</p>
                            <button className="absolute top-2 right-2 p-2 bg-red-500/80 text-white rounded-full hover:bg-red-500">
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}
