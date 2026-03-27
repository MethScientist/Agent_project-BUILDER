using System;
using Game.Core;

namespace Game.Core
{
    public class Health
    {
        public int Current { get; private set; } = 100;

        public void TakeDamage(int amount)
        {
            if (amount < 0) throw new ArgumentException("Damage amount cannot be negative.", nameof(amount));
            Current = Math.Max(Current - amount, 0);
        }
    }
}