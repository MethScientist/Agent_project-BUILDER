namespace Game.Core
{
    public class Health
    {
        public int Current { get; private set; }

        public Health(int initial = 100)
        {
            Current = initial;
        }

        public void TakeDamage(int amount)
        {
            Current -= amount;
            if (Current < 0)
                Current = 0;
        }
    }
}