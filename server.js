const express = require('express');
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

// Vaqtinchalik ma'lumotlar bazasi (Anime ro'yxati)
const animeData = [
  {
    id: "naruto",
    title: "Naruto",
    episodes: {
      1: { title: "1-qism: Bo'ronning boshlanishi", videoUrl: "https://www.youtube.com/embed/dQw4w9WgXcQ" },
      2: { title: "2-qism: Yangi do'stlar", videoUrl: "https://www.youtube.com/embed/dQw4w9WgXcQ" }
    }
  }
];

// Anime va uning qismini qaytaruvchi API endpoint
app.get('/api/watch', (req, res) => {
  const { id, ep } = req.query;
  const anime = animeData.find(a => a.id === id);
  
  if (anime && anime.episodes[ep]) {
    res.json({
      animeTitle: anime.title,
      episodeTitle: anime.episodes[ep].title,
      videoUrl: anime.episodes[ep].videoUrl
    });
  } else {
    res.status(404).json({ message: "Qism topilmadi!" });
  }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Server ${PORT}-portda muvaffaqiyatli ishlayapti!`);
});