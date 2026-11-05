package example;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class OrderController {
    private final OrderService service = new OrderService();

    @PostMapping("/orders")
    public String createOrder() { return service.create(); }
}
