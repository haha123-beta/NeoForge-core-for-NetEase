package util;
public class Tools {
    public static final int BASE = 7;
    public static final String TITLE = "static imports";
    public static int add(int left, int right) { return left + right; }
    public static int choose(int value) { return value + 2; }
    public static int choose(Object value) { return 9; }
}
