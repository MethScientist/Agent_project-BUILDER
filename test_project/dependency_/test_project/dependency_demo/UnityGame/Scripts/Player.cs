using Game.Core;
using Game;

namespace Game
{
    public class Player
    {
        private Health health = new Health();

        public void Hit(int dmg)
        {
            health.TakeDamage(dmg);
        }
    }
}