using System;
using UnityGame;

namespace Game.Core
{
    public class Health
    {
        public int Current = 100;

        public void TakeDamage(int amount)
        {
            if (amount <= 0) return;
            Current = Math.Max(Current - amount, 0);
        }
    }
}
# BEGIN Implement Health.cs with namespace Game.Core, class Health, int Current property and TakeDamage(int amount) method
using System;

namespace Game.Core
{
    public class Health
    {
        public int Current = 100;

        public void TakeDamage(int amount)
        {
            if (amount <= 0) return;
            Current = Math.Max(Current - amount, 0);
        }
    }
}
# END Implement Health.cs with namespace Game.Core, class Health, int Current property and TakeDamage(int amount) method
