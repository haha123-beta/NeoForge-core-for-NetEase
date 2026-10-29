package sample;
public class Box {
    private int count;
    public Box(int start) { this.count = start; }
    public int read() { return count; }
    public boolean is() { return true; }
    public String hello() { return "中文"; }
}
