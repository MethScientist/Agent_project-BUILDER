using Game.Core;
using UnityGame.Scripts;

namespace Game
{
    public class Player
    {
        private Health health;

        public Player()
        {
            health = new Health();
        }

        public void Hit(int dmg)
        {
            health.TakeDamage(dmg);
        }
    }
}
# BEGIN Implement Player.cs with namespace Game, using Game.Core, a Health field and Hit(int dmg) method that calls Health.TakeD
using Game.Core;

namespace Game
{
    public class Player
    {
        private Health health;

        public Player()
        {
            health = new Health();
        }

        public void Hit(int dmg)
        {
            health.TakeDamage(dmg);
        }
    }
}
# END Implement Player.cs with namespace Game, using Game.Core, a Health field and Hit(int dmg) method that calls Health.TakeD
