package edu.purdue.cs536.stream;

public interface Trace {
    void event(String event, Frame frame, String detail);
    Trace NONE = (event, frame, detail) -> { };
}
