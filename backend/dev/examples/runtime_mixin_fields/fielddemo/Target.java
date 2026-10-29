package fielddemo;
public class Target {
 private final int value;
 public Target(int n){value=n;}
 public int read(){return value;}
 public boolean enabled(int n){return n>0;}
}
